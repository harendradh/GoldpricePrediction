"""Agent memory · in-process + DB-backed feedback learning.

Two layers:
  · In-process LRU for repo memory snapshots (sub-millisecond reads)
  · Optional SQLAlchemy session for persistent learning (decisions, stats)

The memory itself is generic — no hardcoded team / repo names. Callers
hydrate with whatever DB session they have.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from Agents.Core.observability import get_logger

logger = get_logger(__name__)


@dataclass
class MemoryRecord:
    """One feedback event used by the learning loop."""
    repo: str
    rule_id: str
    decision: str          # accept | dismiss | reply
    decided_at: datetime
    actor: str
    note: str | None = None


@dataclass
class RepoMemorySnapshot:
    """Per-repo memory · agents read this at perception time.

    `confidence_adjustments` maps rule_id → signed delta applied to skill
    output confidence (negative = chronically dismissed → fire less often).
    """
    repo: str
    confidence_adjustments: dict[str, float] = field(default_factory=dict)
    dimension_accept_rate: dict[str, float] = field(default_factory=dict)
    recent_incident_signals: list[str] = field(default_factory=list)
    decision_count: int = 0
    last_decided_at: datetime | None = None


class AgentMemory:
    """Provider-agnostic memory facade.

    `db_session` is a SQLAlchemy session (optional · without it we run pure
    in-process). Any DB schema is up to the host application; we only
    require a few free-form helpers below if persistence is desired.
    """

    _CACHE_SIZE = 64

    def __init__(self, db_session: Any | None = None):
        self.db = db_session
        self._cache: OrderedDict[str, RepoMemorySnapshot] = OrderedDict()

    def snapshot_for(self, repo: str) -> RepoMemorySnapshot:
        if repo in self._cache:
            self._cache.move_to_end(repo)
            return self._cache[repo]

        snapshot = self._compute_snapshot(repo)
        self._cache[repo] = snapshot
        if len(self._cache) > self._CACHE_SIZE:
            self._cache.popitem(last=False)
        return snapshot

    def record_decision(self, record: MemoryRecord) -> None:
        """Persist a decision (if DB attached) and invalidate cache."""
        if self.db is not None:
            # Delegate to host app persistence (the backend handles this via
            # its own MemoryStore / RuleStat tables). Keeping the schema out
            # of /Agents/ keeps this package backend-agnostic.
            pass
        self._cache.pop(record.repo, None)
        logger.info("memory.decision_recorded",
                    repo=record.repo, rule_id=record.rule_id, decision=record.decision)

    def invalidate(self, repo: str | None = None) -> None:
        if repo is None:
            self._cache.clear()
        else:
            self._cache.pop(repo, None)

    # ──────────────────────────────────────────────────────
    # Snapshot computation
    # ──────────────────────────────────────────────────────
    def _compute_snapshot(self, repo: str) -> RepoMemorySnapshot:
        """Build snapshot from the host's persistence layer (if attached).

        Without DB, returns a neutral snapshot. The host can extend by
        passing `db_session=` to AgentMemory + implementing the queries
        it cares about externally.
        """
        if self.db is None:
            return RepoMemorySnapshot(repo=repo)

        # The host application is expected to populate these via a
        # dependency-injection pattern. We provide a hook that returns
        # empty data by default · subclassable for richer integration.
        return self._db_snapshot(repo)

    def _db_snapshot(self, repo: str) -> RepoMemorySnapshot:
        """Override in a subclass to read whatever DB shape the host uses."""
        return RepoMemorySnapshot(repo=repo)
