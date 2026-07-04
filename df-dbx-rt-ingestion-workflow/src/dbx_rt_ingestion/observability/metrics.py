"""Metric event model: StreamingQueryProgress -> flat, platform-agnostic dict.

Events are plain dicts so every publisher (log, Delta, HTTP) can serialize
them without coupling to Spark classes. Field names are stable — monitoring
dashboards and alerts depend on them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _sum_source_metric(progress: dict[str, Any], metric: str) -> int | None:
    """Sum a per-source metric (e.g. Kafka offsets-behind-latest) if present."""

    total: int | None = None
    for source in progress.get("sources", []):
        value = (source.get("metrics") or {}).get(metric)
        if value is not None:
            total = (total or 0) + int(value)
    return total


def progress_to_event(
    progress: dict[str, Any],
    *,
    app_name: str,
    environment: str,
    run_id: str,
) -> dict[str, Any]:
    """Convert one query progress payload into a metric event."""

    duration = progress.get("durationMs", {}) or {}
    state_operators = progress.get("stateOperators", []) or []
    event_time = progress.get("eventTime", {}) or {}

    return {
        "event_type": "query_progress",
        "framework": "df-dbx-rt-ingestion-workflow",
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "app_name": app_name,
        "environment": environment,
        "run_id": run_id,
        "query_name": progress.get("name"),
        "query_id": progress.get("id"),
        "batch_id": progress.get("batchId"),
        "batch_timestamp": progress.get("timestamp"),
        # throughput
        "input_rows_per_second": progress.get("inputRowsPerSecond"),
        "processed_rows_per_second": progress.get("processedRowsPerSecond"),
        "num_input_rows": progress.get("numInputRows"),
        # latency / batch duration
        "batch_duration_ms": duration.get("triggerExecution"),
        "add_batch_ms": duration.get("addBatch"),
        "get_batch_ms": duration.get("getBatch"),
        "commit_offsets_ms": duration.get("commitOffsets"),
        # consumer lag / backpressure (Kafka publishes offsets-behind-latest)
        "consumer_lag_offsets": _sum_source_metric(
            progress, "estimatedTotalBytesBehindLatest"
        )
        or _sum_source_metric(progress, "offsetsBehindLatest"),
        # watermark
        "watermark": event_time.get("watermark"),
        "event_time_max": event_time.get("max"),
        # state store
        "state_rows_total": sum(
            int(op.get("numRowsTotal", 0)) for op in state_operators
        )
        if state_operators
        else None,
        "state_memory_bytes": sum(
            int(op.get("memoryUsedBytes", 0)) for op in state_operators
        )
        if state_operators
        else None,
        # kafka offsets (start/end per source, JSON-encoded strings)
        "source_start_offsets": [s.get("startOffset") for s in progress.get("sources", [])],
        "source_end_offsets": [s.get("endOffset") for s in progress.get("sources", [])],
        "sink_description": (progress.get("sink") or {}).get("description"),
        "output_rows": (progress.get("sink") or {}).get("numOutputRows"),
    }


def termination_event(
    *,
    app_name: str,
    environment: str,
    run_id: str,
    query_id: str,
    exception: str | None,
) -> dict[str, Any]:
    """Event emitted when a query terminates (exception == None means clean)."""

    return {
        "event_type": "query_terminated",
        "framework": "df-dbx-rt-ingestion-workflow",
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "app_name": app_name,
        "environment": environment,
        "run_id": run_id,
        "query_id": query_id,
        "failed": exception is not None,
        "exception": exception,
    }
