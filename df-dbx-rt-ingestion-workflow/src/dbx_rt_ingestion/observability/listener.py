"""Streaming Query Listener bridging Spark progress events to publishers.

Attached once per application run. Captures consumer lag, throughput,
latency, batch duration, watermark delay, state-store metrics, offsets, and
failure events, then fans out to every configured publisher.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from dbx_rt_ingestion.core.logging import get_logger
from dbx_rt_ingestion.observability.metrics import progress_to_event, termination_event

if TYPE_CHECKING:  # pragma: no cover
    from dbx_rt_ingestion.core.interfaces import MetricsPublisher

_logger = get_logger("listener")


def create_listener(
    *,
    app_name: str,
    environment: str,
    run_id: str,
    publishers: list[MetricsPublisher],
) -> Any:
    """Build the framework StreamingQueryListener.

    Defined as a factory (not a module-level class) because
    StreamingQueryListener is only importable under an active Spark runtime.
    """

    from pyspark.sql.streaming import StreamingQueryListener

    class FrameworkQueryListener(StreamingQueryListener):  # type: ignore[misc]
        """Publishes framework metric events for every managed query."""

        def onQueryStarted(self, event: Any) -> None:  # noqa: N802
            _logger.info(
                "query started",
                extra={"dfx": {"query_id": str(event.id), "query_name": event.name}},
            )

        def onQueryProgress(self, event: Any) -> None:  # noqa: N802
            try:
                progress: dict[str, Any] = json.loads(event.progress.json)
                metric = progress_to_event(
                    progress,
                    app_name=app_name,
                    environment=environment,
                    run_id=run_id,
                )
                self._publish(metric)
            except Exception:  # noqa: BLE001 - listener must never throw
                _logger.exception("failed to process progress event")

        def onQueryTerminated(self, event: Any) -> None:  # noqa: N802
            try:
                exception = getattr(event, "exception", None)
                self._publish(
                    termination_event(
                        app_name=app_name,
                        environment=environment,
                        run_id=run_id,
                        query_id=str(event.id),
                        exception=str(exception) if exception else None,
                    )
                )
            except Exception:  # noqa: BLE001
                _logger.exception("failed to process termination event")

        def onQueryIdle(self, event: Any) -> None:  # noqa: N802
            """No-op; idle events are high-volume and rarely actionable."""

        def _publish(self, metric: dict[str, Any]) -> None:
            for publisher in publishers:
                try:
                    publisher.publish(metric)
                except Exception:  # noqa: BLE001 - publisher contract backstop
                    _logger.exception(
                        "publisher %s failed", type(publisher).__name__
                    )

    return FrameworkQueryListener()
