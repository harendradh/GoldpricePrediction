"""Audit framework.

Writes run- and pipeline-level audit records (who/what/when/how many) to the
configured audit table. Row-level lineage relies on the ``_dfx_*`` envelope
persisted in the sink table (topic, partition, offset, timestamps), which
makes every target row traceable to its exact source record — the basis for
data reconciliation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from dbx_rt_ingestion.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import SparkSession

    from dbx_rt_ingestion.config.models import AppSpec

_logger = get_logger("audit")


class AuditLogger:
    """Persists audit events; degrades to structured logs when no table is set."""

    def __init__(self, spark: SparkSession, app: AppSpec, run_id: str) -> None:
        self.spark = spark
        self.app = app
        self.run_id = run_id
        self.table = app.observability.audit_table

    def record(self, event_type: str, **details: Any) -> None:
        event = {
            "event_type": event_type,
            "app_name": self.app.name,
            "domain": self.app.domain,
            "platform": self.app.platform,
            "app_version": self.app.version,
            "run_id": self.run_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "details": json.dumps(details, default=str),
        }
        _logger.info("audit", extra={"dfx": event})
        if not self.table:
            return
        try:
            self.spark.createDataFrame([event]).write.mode("append").saveAsTable(
                self.table
            )
        except Exception:  # noqa: BLE001 - audit must not stop ingestion
            _logger.exception("audit write failed")

    def run_started(self, pipelines: list[str]) -> None:
        self.record("run_started", pipelines=pipelines, environment_tags=self.app.tags)

    def pipeline_started(self, pipeline_name: str, topic: str) -> None:
        self.record("pipeline_started", pipeline=pipeline_name, topic=topic)

    def run_stopped(self, reason: str) -> None:
        self.record("run_stopped", reason=reason)
