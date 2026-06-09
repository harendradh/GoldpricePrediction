"""Planning module · derives ExecutionPlan from Signals + mode.

Decides which SubAgents to invoke and in what order. Smart-skip
short-circuits to an empty plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Agents.Core.observability import get_logger
from Agents.Core.schemas import PRContext, ReviewMode
from Agents.MasterAgent.reasoning import Signals

logger = get_logger(__name__)


@dataclass
class PlannedSubAgent:
    name: str
    priority: int = 5     # 1 = urgent, 9 = optional
    rationale: str = ""
    parameters: dict = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    plan_id: str
    mode: ReviewMode
    smart_skip: bool
    smart_skip_reason: str | None
    sub_agents: list[PlannedSubAgent]
    parallel: bool = True
    rationale: str = ""

    @property
    def is_empty(self) -> bool:
        return len(self.sub_agents) == 0


class Planning:
    """Translates PRContext + Signals + mode → ExecutionPlan."""

    def plan(self, context: PRContext, signals: Signals, mode: ReviewMode = ReviewMode.DEEP) -> ExecutionPlan:
        if context.smart_skip_eligible:
            return ExecutionPlan(
                plan_id=f"plan-{context.pr_id}",
                mode=mode, smart_skip=True,
                smart_skip_reason=context.smart_skip_reason,
                sub_agents=[],
                rationale=f"smart_skip · {context.smart_skip_reason}",
            )

        sub_agents: list[PlannedSubAgent] = []

        # ─── Always-on ────────────────────────────────────────
        sub_agents.append(PlannedSubAgent(
            name="security_review_agent", priority=1,
            rationale="Security stakes · always evaluated",
        ))
        sub_agents.append(PlannedSubAgent(
            name="code_review_agent", priority=2 if mode == ReviewMode.DEEP else 3,
            rationale="Default code-review dimensions",
        ))

        # ─── Conditional ──────────────────────────────────────
        if mode == ReviewMode.DEEP:
            if signals.has_perf_signal or any(
                lang in context.languages_detected for lang in ("python", "scala", "java", "sql")
            ):
                sub_agents.append(PlannedSubAgent(
                    name="performance_review_agent",
                    priority=2 if signals.has_perf_signal else 4,
                    rationale=f"perf signal={signals.has_perf_signal} · perf-relevant languages present",
                ))
            if signals.has_architecture_signal or signals.has_api_signal or signals.has_migration_signal:
                sub_agents.append(PlannedSubAgent(
                    name="architecture_agent", priority=2,
                    rationale=f"arch={signals.has_architecture_signal} api={signals.has_api_signal} migration={signals.has_migration_signal}",
                ))
            if signals.has_test_signal:
                sub_agents.append(PlannedSubAgent(
                    name="test_coverage_agent", priority=3,
                    rationale="net-new code without tests detected",
                ))
            if signals.has_dep_signal:
                sub_agents.append(PlannedSubAgent(
                    name="dependency_audit_agent", priority=2,
                    rationale="dependency manifest touched",
                ))
            if signals.has_governance_signal or signals.is_release_critical:
                sub_agents.append(PlannedSubAgent(
                    name="governance_agent", priority=3,
                    rationale=f"gov_signal={signals.has_governance_signal} release_critical={signals.is_release_critical}",
                ))

        # Sort by priority ASC
        sub_agents.sort(key=lambda s: s.priority)

        plan = ExecutionPlan(
            plan_id=f"plan-{context.pr_id}",
            mode=mode, smart_skip=False, smart_skip_reason=None,
            sub_agents=sub_agents, parallel=True,
            rationale=(f"mode={mode.value} · "
                       f"sub_agents={[s.name for s in sub_agents]} · "
                       f"signals={signals.risk_indicators}"),
        )
        logger.info("planning.plan_built", pr=context.pr_number,
                    sub_agents=len(sub_agents), mode=mode.value)
        return plan
