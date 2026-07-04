"""Pipeline runner: application lifecycle orchestration.

Responsibilities:
1. Configure logging + audit for the run.
2. Validate the spec against all registries (fail fast).
3. Attach the framework StreamingQueryListener.
4. Start every topic pipeline.
5. Supervise: restart failed pipelines under the retry policy, honor
   graceful-shutdown markers, stop cleanly.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from dbx_rt_ingestion.audit.audit import AuditLogger
from dbx_rt_ingestion.config.validation import validate_app_spec
from dbx_rt_ingestion.core.exceptions import PipelineError
from dbx_rt_ingestion.core.logging import configure_logging, get_logger
from dbx_rt_ingestion.observability.listener import create_listener
from dbx_rt_ingestion.observability.publishers import build_publishers
from dbx_rt_ingestion.pipeline.builder import PipelineBuilder, TopicPipeline
from dbx_rt_ingestion.reliability.retry import RetryPolicy
from dbx_rt_ingestion.reliability.shutdown import GracefulShutdown

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import SparkSession
    from pyspark.sql.streaming import StreamingQuery

    from dbx_rt_ingestion.config.loader import SpecLoader
    from dbx_rt_ingestion.config.models import AppSpec

_SUPERVISION_INTERVAL_SECONDS = 15


class PipelineRunner:
    """Runs one application spec to completion (or until shutdown)."""

    def __init__(self, spark: SparkSession, spec: AppSpec, loader: SpecLoader) -> None:
        self.spark = spark
        self.spec = spec
        self.loader = loader
        self.run_id = uuid.uuid4().hex[:12]

        configure_logging(
            app_name=spec.name,
            environment=loader.environment,
            run_id=self.run_id,
            platform=spec.platform,
            level=spec.observability.log_level,
        )
        self._logger = get_logger("runner")
        self._shutdown = GracefulShutdown(spec.reliability.graceful_shutdown_marker)
        self._retry = RetryPolicy(spec.reliability.retry)
        self._audit = AuditLogger(spark, spec, self.run_id)
        self._active: dict[str, list[StreamingQuery]] = {}
        self._attempts: dict[str, int] = {}

    # -------------------------------------------------------------------- run
    def run(self, await_termination: bool = True) -> None:
        validate_app_spec(self.spec)

        publishers = build_publishers(self.spec.observability.publishers)
        listener = create_listener(
            app_name=self.spec.name,
            environment=self.loader.environment,
            run_id=self.run_id,
            publishers=publishers,
        )
        self.spark.streams.addListener(listener)

        pipelines = PipelineBuilder(self.spark, self.spec, self.loader).build()
        self._audit.run_started([p.name for p in pipelines])

        for pipeline in pipelines:
            self._start_pipeline(pipeline)

        if await_termination:
            try:
                self._supervise(pipelines)
            finally:
                self.spark.streams.removeListener(listener)
                for publisher in publishers:
                    publisher.close()

    # -------------------------------------------------------------- internals
    def _start_pipeline(self, pipeline: TopicPipeline) -> None:
        self._audit.pipeline_started(
            pipeline.name, pipeline.ctx.topic.name if pipeline.ctx.topic else ""
        )
        self._active[pipeline.name] = pipeline.start()
        self._logger.info(
            "pipeline started", extra={"dfx": {"pipeline": pipeline.name}}
        )

    def _supervise(self, pipelines: list[TopicPipeline]) -> None:
        """Health-check loop: restart failures, honor shutdown, exit when done."""

        by_name = {p.name: p for p in pipelines}
        try:
            while True:
                if self._shutdown.requested():
                    self._stop_everything("graceful_shutdown")
                    return

                any_active = False
                for name, queries in list(self._active.items()):
                    failed = [q for q in queries if q.exception() is not None]
                    if failed:
                        self._handle_failure(by_name[name], failed[0])
                    any_active = any_active or any(q.isActive for q in queries)

                if not any_active:
                    self._audit.run_stopped("all_queries_finished")
                    return
                time.sleep(_SUPERVISION_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            self._stop_everything("keyboard_interrupt")

    def _handle_failure(self, pipeline: TopicPipeline, query: StreamingQuery) -> None:
        error = query.exception()
        self._logger.error(
            "pipeline failed",
            extra={"dfx": {"pipeline": pipeline.name, "error": str(error)}},
        )
        if self.spec.reliability.fail_fast:
            self._stop_everything("fail_fast")
            raise PipelineError(
                f"Pipeline '{pipeline.name}' failed with fail_fast enabled",
                context={"error": str(error)},
            )

        attempts = self._attempts.get(pipeline.name, 0) + 1
        self._attempts[pipeline.name] = attempts
        if attempts > self.spec.reliability.retry.max_attempts:
            self._stop_everything("retry_exhausted")
            raise PipelineError(
                f"Pipeline '{pipeline.name}' exhausted "
                f"{self.spec.reliability.retry.max_attempts} restart attempts",
                context={"error": str(error)},
            )

        delay = self._retry.backoff_seconds(attempts)
        self._logger.warning(
            "restarting pipeline",
            extra={
                "dfx": {
                    "pipeline": pipeline.name,
                    "attempt": attempts,
                    "backoff_seconds": round(delay, 1),
                }
            },
        )
        self._shutdown.stop_all(self._active.get(pipeline.name, []))
        time.sleep(delay)
        self._start_pipeline(pipeline)

    def _stop_everything(self, reason: str) -> None:
        all_queries = [q for queries in self._active.values() for q in queries]
        self._shutdown.stop_all(all_queries)
        self._audit.run_stopped(reason)
        self._logger.info("run stopped", extra={"dfx": {"reason": reason}})
