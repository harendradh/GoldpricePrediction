"""Action module · executes the ExecutionPlan with bounded parallelism.

Each PlannedSubAgent is mapped to its SubAgent instance and invoked.
Findings + telemetry are aggregated; failures of one sub-agent don't
kill peers.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from Agents.Core.model import DatabricksClaude
from Agents.Core.observability import get_logger, trace_span
from Agents.Core.schemas import Finding, PRContext, ReviewVerdict, Severity, SkillContext
from Agents.MasterAgent.planning import ExecutionPlan
from Agents.SubAgents import (
    ArchitectureAgent, CABDocumentAgent, CodeReviewAgent, DependencyAuditAgent,
    GovernanceAgent, PerformanceReviewAgent, ReleaseReadinessAgent, ScorecardAgent,
    SecurityReviewAgent, TestCoverageAgent,
)
from Agents.SubAgents.base import SubAgent, SubAgentResult

logger = get_logger(__name__)

_MAX_CONCURRENT = 4

# Static registry maps planned sub-agent names → instances
_SUB_AGENTS: dict[str, SubAgent] = {
    a.name: a for a in [
        CodeReviewAgent(), SecurityReviewAgent(), PerformanceReviewAgent(),
        ArchitectureAgent(), TestCoverageAgent(), DependencyAuditAgent(),
        GovernanceAgent(), CABDocumentAgent(), ScorecardAgent(),
        ReleaseReadinessAgent(),
    ]
}


@dataclass
class ActionOutcome:
    plan_id: str
    success: bool
    duration_ms: int
    sub_agent_results: list[SubAgentResult] = field(default_factory=list)
    aggregated_findings: list[Finding] = field(default_factory=list)
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    verdict: ReviewVerdict = ReviewVerdict.MERGE
    total_cost_usd: float = 0.0
    total_model_calls: int = 0


class Action:
    """Runs an ExecutionPlan."""

    def __init__(self, model: DatabricksClaude | None = None):
        self.model = model
        self.semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    @trace_span("master.action.execute")
    async def execute(
        self,
        plan: ExecutionPlan,
        context: PRContext,
        memory: dict[str, Any] | None = None,
    ) -> ActionOutcome:
        if plan.is_empty:
            return ActionOutcome(
                plan_id=plan.plan_id, success=True, duration_ms=0,
                verdict=ReviewVerdict.SMART_SKIP,
            )

        ctx = SkillContext(pr=context, memory=memory or {}, parameters={})

        async def _run_one(planned) -> SubAgentResult:
            agent = _SUB_AGENTS.get(planned.name)
            if agent is None:
                return SubAgentResult(
                    agent_name=planned.name, success=False, duration_ms=0,
                    error=f"sub-agent '{planned.name}' not registered",
                )
            async with self.semaphore:
                return await agent.execute(ctx, self.model)

        tasks = [asyncio.create_task(_run_one(p)) for p in plan.sub_agents]
        results: list[SubAgentResult] = await asyncio.gather(*tasks, return_exceptions=False)

        # Aggregate findings
        all_findings: list[Finding] = []
        for r in results:
            if r.success:
                all_findings.extend(r.findings)
        deduped = self._dedupe(all_findings)
        ranked = self._rank(deduped)
        by_sev = self._severity_breakdown(ranked)
        verdict = self._compute_verdict(ranked)
        cost = sum(r.estimated_cost_usd for r in results)
        mc = sum(r.model_calls for r in results)
        duration = sum(r.duration_ms for r in results)

        return ActionOutcome(
            plan_id=plan.plan_id,
            success=all(r.success for r in results),
            duration_ms=duration,
            sub_agent_results=results,
            aggregated_findings=ranked,
            findings_by_severity=by_sev,
            verdict=verdict,
            total_cost_usd=round(cost, 6),
            total_model_calls=mc,
        )

    @staticmethod
    def _dedupe(findings: list[Finding]) -> list[Finding]:
        bucketed: dict[tuple[str, str, int], Finding] = {}
        for f in findings:
            key = (f.rule_id, f.file, f.line_start)
            existing = bucketed.get(key)
            if existing is None or f.confidence > existing.confidence:
                bucketed[key] = f
        return list(bucketed.values())

    @staticmethod
    def _rank(findings: list[Finding]) -> list[Finding]:
        return sorted(findings, key=lambda f: (f.severity.order, -f.confidence, f.file, f.line_start))

    @staticmethod
    def _severity_breakdown(findings: list[Finding]) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in findings:
            out[f.severity.value] = out.get(f.severity.value, 0) + 1
        return out

    @staticmethod
    def _compute_verdict(findings: list[Finding]) -> ReviewVerdict:
        if any(f.severity == Severity.BLOCKER for f in findings):
            return ReviewVerdict.BLOCK
        if any(f.severity == Severity.MAJOR for f in findings):
            return ReviewVerdict.IMPROVE
        return ReviewVerdict.MERGE
