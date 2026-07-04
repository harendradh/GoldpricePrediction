"""Pipeline builder: spec -> executable topic pipelines.

For each topic the builder wires:
    source.read -> parser.parse -> quality rules -> DLQ split
        valid -> (optional watermark) -> sink        (main query)
        dead  -> DLQ table                           (side query)

Each pipeline is independent: its own checkpoint, its own queries, its own
failure/retry lifecycle in the runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dbx_rt_ingestion.config.models import AppSpec, TopicSpec
from dbx_rt_ingestion.core.context import PipelineContext
from dbx_rt_ingestion.core.logging import get_logger
from dbx_rt_ingestion.quality.rules import apply_quality_rules
from dbx_rt_ingestion.reliability.dlq import DeadLetterQueue
from dbx_rt_ingestion.transform.mapping import apply_mapping

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import SparkSession
    from pyspark.sql.streaming import StreamingQuery

    from dbx_rt_ingestion.config.loader import SpecLoader

_logger = get_logger("builder")


@dataclass
class TopicPipeline:
    """One runnable topic pipeline (start() is idempotent per run)."""

    ctx: PipelineContext
    _builder: PipelineBuilder

    @property
    def name(self) -> str:
        return self.ctx.pipeline_name

    def start(self) -> list[StreamingQuery]:
        """Start the main (and DLQ) streaming queries for this topic."""

        return self._builder.start_topic(self.ctx)


class PipelineBuilder:
    """Builds topic pipelines from a validated application spec."""

    def __init__(self, spark: SparkSession, spec: AppSpec, loader: SpecLoader) -> None:
        from dbx_rt_ingestion.schema.resolver import SchemaResolver

        self.spark = spark
        self.spec = spec
        self.loader = loader
        self.environment = loader.environment
        self._schema_resolver = SchemaResolver(spec.schema_management)
        self._cluster = (
            loader.load_cluster_spec(spec.source.cluster) if spec.source.cluster else None
        )

    def build(self) -> list[TopicPipeline]:
        """One pipeline per topic entry."""

        pipelines = []
        for topic in self.spec.source.topics:
            schema = (
                self._schema_resolver.resolve(topic.schema_ref)
                if topic.schema_ref
                else None
            )
            ctx = PipelineContext(
                spark=self.spark,
                app=self.spec,
                environment=self.environment,
                topic=topic,
                schema=schema,
            )
            pipelines.append(TopicPipeline(ctx=ctx, _builder=self))
            _logger.info(
                "pipeline built",
                extra={
                    "dfx": {
                        "pipeline": ctx.pipeline_name,
                        "topic": topic.name,
                        "parser": topic.parser.type,
                        "schema": f"{schema.subject}@{schema.version}" if schema else None,
                    }
                },
            )
        return pipelines

    # ------------------------------------------------------------------ wiring
    def start_topic(self, ctx: PipelineContext) -> list[StreamingQuery]:
        from dbx_rt_ingestion.parsers.base import parser_registry
        from dbx_rt_ingestion.sinks.base import sink_registry
        from dbx_rt_ingestion.sources.base import source_registry

        topic = ctx.topic
        assert topic is not None  # builder only creates topic contexts

        source = source_registry.create(
            self.spec.source.type,
            source_spec=self.spec.source,
            cluster_spec=self._cluster,
            topic_spec=topic,
        )
        parser = parser_registry.create(topic.parser.type, spec=topic.parser)
        sink_spec = topic.sink or self.spec.sink
        sink = sink_registry.create(sink_spec.type, spec=sink_spec)

        raw = source.read(ctx)
        parsed = parser.parse(raw, ctx)
        checked = apply_quality_rules(parsed, topic.quality)

        queries: list[StreamingQuery] = []
        if self.spec.reliability.dlq.enabled:
            dlq = DeadLetterQueue(ctx)
            valid, dead = DeadLetterQueue.split(checked)
            queries.append(dlq.write(dead))
        else:
            valid = checked

        valid = apply_mapping(valid, topic.mapping)

        if topic.watermark:
            valid = valid.withWatermark(
                topic.watermark["column"], topic.watermark["delay"]
            )

        queries.insert(0, sink.write(valid.drop("_dfx_error"), ctx))
        return queries


def build_topic_pipeline_for_test(ctx: PipelineContext, spec: TopicSpec) -> None:
    """Placeholder hook for test harnesses (kept intentionally minimal)."""
