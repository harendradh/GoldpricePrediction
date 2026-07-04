"""Retry framework with exponential backoff.

Used by the runner to restart failed pipelines and available as a decorator
for any transient-failure-prone operation (schema registry calls, sink setup).
"""

from __future__ import annotations

import functools
import random
import time
from collections.abc import Callable
from typing import TypeVar

from dbx_rt_ingestion.config.models import RetrySpec
from dbx_rt_ingestion.core.exceptions import RetryExhaustedError
from dbx_rt_ingestion.core.logging import get_logger

T = TypeVar("T")
_logger = get_logger("retry")


class RetryPolicy:
    """Executes callables under the spec's retry/backoff settings."""

    def __init__(self, spec: RetrySpec) -> None:
        self.spec = spec

    def backoff_seconds(self, attempt: int) -> float:
        """Exponential backoff with +/-20% jitter; attempt is 1-based."""

        base = self.spec.initial_backoff_seconds * (
            self.spec.backoff_multiplier ** (attempt - 1)
        )
        capped = min(base, self.spec.max_backoff_seconds)
        return capped * random.uniform(0.8, 1.2)

    def run(self, operation: Callable[[], T], *, name: str = "operation") -> T:
        last_error: BaseException | None = None
        for attempt in range(1, self.spec.max_attempts + 1):
            try:
                return operation()
            except Exception as exc:  # noqa: BLE001 - retry boundary
                last_error = exc
                if attempt == self.spec.max_attempts:
                    break
                delay = self.backoff_seconds(attempt)
                _logger.warning(
                    "retryable failure in %s (attempt %d/%d), backing off %.1fs: %s",
                    name,
                    attempt,
                    self.spec.max_attempts,
                    delay,
                    exc,
                )
                time.sleep(delay)
        raise RetryExhaustedError(
            f"'{name}' failed after {self.spec.max_attempts} attempt(s)",
            context={"attempts": self.spec.max_attempts},
            cause=last_error,
        )


def retryable(spec: RetrySpec) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator form of :class:`RetryPolicy`."""

    policy = RetryPolicy(spec)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> T:
            return policy.run(lambda: func(*args, **kwargs), name=func.__qualname__)

        return wrapper

    return decorator
