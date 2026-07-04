"""Standardized structured logging.

All framework and application logs are emitted as single-line JSON so they can
be ingested by enterprise log platforms (Splunk, CloudWatch, Datadog) without
custom parsing. Every record carries the application, platform, environment,
and run identity injected by :func:`configure_logging`.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

_CONTEXT: dict[str, str] = {}


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON with framework context."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_CONTEXT,
        }
        extra = getattr(record, "dfx", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(
    *,
    app_name: str,
    environment: str,
    run_id: str,
    platform: str | None = None,
    level: str = "INFO",
) -> None:
    """Configure root logging once per application run."""

    _CONTEXT.update(
        {
            "framework": "df-dbx-rt-ingestion-workflow",
            "app_name": app_name,
            "environment": environment,
            "run_id": run_id,
        }
    )
    if platform:
        _CONTEXT["platform"] = platform

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("dfx")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced framework logger (``dfx.<name>``)."""

    return logging.getLogger(f"dfx.{name}")


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    """Log ``message`` with structured ``fields`` attached."""

    logger.log(level, message, extra={"dfx": fields})
