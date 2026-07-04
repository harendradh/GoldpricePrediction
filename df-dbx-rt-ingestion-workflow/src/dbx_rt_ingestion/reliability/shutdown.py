"""Graceful shutdown.

Operations teams request a clean stop by creating a marker file (e.g. on a
UC volume) at ``reliability.graceful_shutdown_marker``. The runner polls the
marker between health checks and stops each query after its in-flight
micro-batch completes — checkpoints stay consistent, restart is clean.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dbx_rt_ingestion.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql.streaming import StreamingQuery

_logger = get_logger("shutdown")


class GracefulShutdown:
    """File-marker based cooperative shutdown for a set of streaming queries."""

    def __init__(self, marker_path: str | None) -> None:
        self.marker_path = marker_path
        self._requested = False

    def requested(self) -> bool:
        """True once shutdown has been requested (marker seen or manual)."""

        if self._requested:
            return True
        if self.marker_path and os.path.exists(self.marker_path):
            _logger.info("shutdown marker detected at %s", self.marker_path)
            self._requested = True
        return self._requested

    def request(self) -> None:
        """Programmatic shutdown request (signal handlers, tests)."""

        self._requested = True

    def stop_all(self, queries: list[StreamingQuery]) -> None:
        """Stop every active query; StreamingQuery.stop waits for the batch."""

        for query in queries:
            if query.isActive:
                _logger.info("stopping query %s", query.name)
                try:
                    query.stop()
                except Exception:  # noqa: BLE001 - best-effort shutdown
                    _logger.exception("failed to stop query %s", query.name)
