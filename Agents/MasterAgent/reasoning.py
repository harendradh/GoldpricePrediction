"""Reasoning module · interprets PRContext + memory to derive signals.

This is where domain inference happens: what kind of change is this,
which dimensions matter most, what's the prior history telling us about
this repo's review patterns.

The output is a set of structured Signals consumed by Planning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from Agents.Core.observability import get_logger, trace_span
from Agents.Core.schemas import PRContext

logger = get_logger(__name__)


@dataclass
class Signals:
    """What Reasoning produces · consumed by Planning."""
    has_security_signal: bool = False
    has_perf_signal: bool = False
    has_architecture_signal: bool = False
    has_governance_signal: bool = False
    has_dep_signal: bool = False
    has_migration_signal: bool = False
    has_api_signal: bool = False
    has_test_signal: bool = False

    is_large_change: bool = False
    is_release_critical: bool = False
    is_rollback: bool = False

    priority_dimensions: list[str] = field(default_factory=list)
    risk_indicators: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Reasoning:
    """Domain inference over PRContext + memory snapshot."""

    @trace_span("master.reasoning.infer")
    def infer(self, context: PRContext, memory: dict[str, Any]) -> Signals:
        sigs = Signals()
        path_concat = " ".join(f.path for f in context.files).lower()
        title_low = context.title.lower()

        # ─── Security signals ─────────────────────────────────
        if "security" in context.inferred_priorities:
            sigs.has_security_signal = True
        if any(p in path_concat for p in ("/auth", "/security", "/crypto", "config")):
            sigs.has_security_signal = True

        # ─── Performance ──────────────────────────────────────
        if "performance" in context.inferred_priorities:
            sigs.has_perf_signal = True
        if any(lang in {"scala", "python"} for lang in context.languages_detected) and "spark" in path_concat:
            sigs.has_perf_signal = True

        # ─── Architecture / API ───────────────────────────────
        if any(p in path_concat for p in ("/api/", "/controllers/", "openapi", ".proto", ".graphql")):
            sigs.has_architecture_signal = True
            sigs.has_api_signal = True
        if any(f.is_migration for f in context.files):
            sigs.has_migration_signal = True
            sigs.has_architecture_signal = True
        if any(p in path_concat for p in ("/db/models", "alembic")):
            sigs.has_migration_signal = True

        # ─── Governance ───────────────────────────────────────
        if any(p in path_concat for p in ("codeowners", "owners")):
            sigs.has_governance_signal = True
        if any(p in path_concat for p in ("/release/", "/deploy/")):
            sigs.has_governance_signal = True

        # ─── Dependencies ─────────────────────────────────────
        deps_manifests = ("requirements.txt", "pyproject.toml", "package.json",
                          "pom.xml", "build.gradle", "go.mod", "Cargo.toml")
        if any(m in path_concat for m in deps_manifests):
            sigs.has_dep_signal = True

        # ─── Test coverage ────────────────────────────────────
        non_test = sum(1 for f in context.files if not f.is_test_file and not f.is_generated)
        has_test = any(f.is_test_file for f in context.files)
        if non_test > 0 and not has_test:
            sigs.has_test_signal = True
            sigs.risk_indicators.append("net-new code without tests in this PR")

        # ─── Volume / release indicators ──────────────────────
        sigs.is_large_change = (context.total_additions + context.total_deletions) > 500
        if sigs.is_large_change:
            sigs.risk_indicators.append("large change > 500 lines")
        sigs.is_release_critical = any(w in title_low for w in ("hotfix", "release", "critical"))
        sigs.is_rollback = any(w in title_low for w in ("revert", "rollback", "undo"))

        # ─── Priority dimensions (from inferred + signals) ───
        sigs.priority_dimensions = list(context.inferred_priorities.keys())

        # ─── Memory-driven notes ─────────────────────────────
        adj = (memory or {}).get("confidence_adjustments") or {}
        if adj:
            sigs.notes.append(f"{len(adj)} repo-tuned rules will adjust confidence")

        logger.info("reasoning.signals", pr=context.pr_number,
                    security=sigs.has_security_signal, perf=sigs.has_perf_signal,
                    arch=sigs.has_architecture_signal, large=sigs.is_large_change)
        return sigs
