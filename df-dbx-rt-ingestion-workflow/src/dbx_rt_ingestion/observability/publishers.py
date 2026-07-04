"""Metrics publishers.

A publisher forwards metric events to a monitoring platform. Publishers MUST
swallow their own failures (log-and-continue) — observability must never take
down the stream it observes.

Built-ins: log (structured stdout), delta (metrics table), http (REST POST).
Enterprise platforms (Prometheus push, Datadog, CloudWatch, Splunk HEC) plug
in via ``@publisher_registry.register``.
"""

from __future__ import annotations

import json
from typing import Any

from dbx_rt_ingestion.core.interfaces import MetricsPublisher
from dbx_rt_ingestion.core.logging import get_logger
from dbx_rt_ingestion.core.registry import Registry

publisher_registry: Registry[MetricsPublisher] = Registry("metrics publisher")

_logger = get_logger("observability")


@publisher_registry.register("log")
class LogPublisher(MetricsPublisher):
    """Emits events as structured JSON logs (baseline; always safe)."""

    def __init__(self, options: dict[str, str] | None = None) -> None:
        self.options = options or {}

    def publish(self, event: dict[str, Any]) -> None:
        _logger.info("metric", extra={"dfx": event})


@publisher_registry.register("delta")
class DeltaPublisher(MetricsPublisher):
    """Appends events to a Delta metrics table (options: table)."""

    def __init__(self, options: dict[str, str] | None = None) -> None:
        options = options or {}
        self.table = options.get("table", "")
        if not self.table:
            raise ValueError("delta publisher requires 'table' option")

    def publish(self, event: dict[str, Any]) -> None:
        try:
            from pyspark.sql import SparkSession

            spark = SparkSession.getActiveSession()
            if spark is None:
                return
            row = {"event_json": json.dumps(event, default=str)}
            spark.createDataFrame([row]).write.mode("append").saveAsTable(self.table)
        except Exception:  # noqa: BLE001 - never fail the stream
            _logger.exception("delta metrics publish failed")


@publisher_registry.register("http")
class HttpPublisher(MetricsPublisher):
    """POSTs events as JSON (options: url, auth_header, timeout_seconds)."""

    def __init__(self, options: dict[str, str] | None = None) -> None:
        options = options or {}
        self.url = options.get("url", "")
        if not self.url:
            raise ValueError("http publisher requires 'url' option")
        self.auth_header = options.get("auth_header")
        self.timeout = float(options.get("timeout_seconds", "10"))

    def publish(self, event: dict[str, Any]) -> None:
        try:
            import requests

            headers = {"Content-Type": "application/json"}
            if self.auth_header:
                headers["Authorization"] = self.auth_header
            requests.post(
                self.url,
                data=json.dumps(event, default=str),
                headers=headers,
                timeout=self.timeout,
            )
        except Exception:  # noqa: BLE001 - never fail the stream
            _logger.exception("http metrics publish failed")


def build_publishers(specs: list[Any]) -> list[MetricsPublisher]:
    """Instantiate every publisher configured in the observability spec."""

    return [
        publisher_registry.create(spec.type, options=dict(spec.options)) for spec in specs
    ]
