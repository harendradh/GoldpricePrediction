"""Structured logging + correlation IDs + trace spans."""
from __future__ import annotations

import contextvars
import time
import uuid
from contextlib import contextmanager
from typing import Any, Generator

import structlog

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agent_correlation_id", default=None
)


def get_logger(name: str) -> structlog.BoundLogger:
    log = structlog.get_logger(name)
    cid = _correlation_id.get()
    if cid:
        log = log.bind(correlation_id=cid)
    return log


def new_correlation_id(prefix: str = "run") -> str:
    cid = f"{prefix}-{uuid.uuid4().hex[:12]}"
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str | None:
    return _correlation_id.get()


@contextmanager
def trace_span(name: str, **attrs: Any) -> Generator[dict[str, Any], None, None]:
    log = get_logger("agents.trace")
    span: dict[str, Any] = dict(attrs)
    t0 = time.perf_counter()
    log.info("span.start", span=name, **attrs)
    try:
        yield span
    except Exception as exc:
        dt = int((time.perf_counter() - t0) * 1000)
        log.error("span.error", span=name, duration_ms=dt, error=str(exc)[:300], **span)
        raise
    else:
        dt = int((time.perf_counter() - t0) * 1000)
        log.info("span.end", span=name, duration_ms=dt, **span)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
