"""Master Agent · orchestrates Perception → Reasoning → Planning → Action."""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from Agents.Core.model import DatabricksClaude
from Agents.Core.memory import AgentMemory
from Agents.Core.observability import get_logger, new_correlation_id
from Agents.Core.schemas import (
    AgentRunRecord, PRContext, ReviewMode, ReviewVerdict, ScorecardMetrics,
    SkillContext, WorkflowResult,
)
from Agents.MasterAgent.action import Action
from Agents.MasterAgent.perception import Perception
from Agents.MasterAgent.planning import Planning
from Agents.MasterAgent.reasoning import Reasoning
from Agents.SubAgents.CABDocumentAgent.agent import CABDocumentAgent
from Agents.SubAgents.ScorecardAgent.agent import ScorecardAgent

logger = get_logger(__name__)


class MasterAgent:
    """Top-level orchestrator with explicit modular pipeline.

    Lifecycle (every invocation):
      1. Perceive    → PRContext
      2. Reason      → Signals
      3. Plan        → ExecutionPlan (sub-agents to invoke)
      4. Act         → ActionOutcome (executes sub-agents)
      5. Remember    → AgentRunRecord + payload

    Public entrypoints:
      · review_pr(...)         — full code review pipeline
      · generate_cab_brief(...)— CAB document generation
      · generate_scorecard(...)— scorecard snapshot
    """

    def __init__(
        self,
        model: DatabricksClaude | None = None,
        memory: AgentMemory | None = None,
    ):
        self.model = model or DatabricksClaude()
        self.memory = memory or AgentMemory()
        self.perception = Perception()
        self.reasoning = Reasoning()
        self.planning = Planning()
        self.action = Action(model=self.model)

    # ─────────────────────────────────────────────────────
    # Code Review (the main loop)
    # ─────────────────────────────────────────────────────
    async def review_pr(
        self,
        *,
        pr_id: int,
        repo: str,
        pr_number: int,
        title: str,
        author: str,
        branch: str,
        diff_text: str,
        description: str = "",
        base_branch: str = "main",
        mode: ReviewMode = ReviewMode.DEEP,
    ) -> dict[str, Any]:
        run_id = f"master-{uuid.uuid4().hex[:12]}"
        new_correlation_id(prefix="master")
        record = AgentRunRecord(
            run_id=run_id, agent_name="master_agent",
            started_at=datetime.utcnow(), pr_id=pr_id, repo=repo,
        )
        start = time.perf_counter()
        logger.info("master.review.start", run_id=run_id, pr=pr_number, mode=mode.value)

        # 1. Perception
        ctx = self.perception.build(
            pr_id=pr_id, repo=repo, pr_number=pr_number,
            title=title, description=description, author=author,
            branch=branch, base_branch=base_branch, diff_text=diff_text,
        )

        # 2. Recall memory
        memory_snap = self.memory.snapshot_for(repo)
        memory_dict = {
            "confidence_adjustments": memory_snap.confidence_adjustments,
            "dimension_accept_rate": memory_snap.dimension_accept_rate,
        }

        # 3. Reason
        signals = self.reasoning.infer(ctx, memory_dict)

        # 4. Plan
        plan = self.planning.plan(ctx, signals, mode=mode)

        # 5. Act
        outcome = await self.action.execute(plan, ctx, memory_dict)

        # 6. Remember
        record.completed_at = datetime.utcnow()
        record.duration_ms = int((time.perf_counter() - start) * 1000)
        record.findings_count = len(outcome.aggregated_findings)
        record.blocker_count = sum(1 for f in outcome.aggregated_findings
                                    if f.severity.value == "BLOCKER")
        record.verdict = outcome.verdict
        record.sub_agents_invoked = [r.agent_name for r in outcome.sub_agent_results]
        record.model_calls = outcome.total_model_calls
        record.estimated_cost_usd = outcome.total_cost_usd

        return {
            "ok": True,
            "run_id": run_id,
            "mode": mode.value,
            "pr_id": pr_id, "repo": repo, "pr_number": pr_number,
            "verdict": outcome.verdict.value,
            "smart_skip": outcome.verdict == ReviewVerdict.SMART_SKIP,
            "smart_skip_reason": ctx.smart_skip_reason,
            "plan": {
                "id": plan.plan_id,
                "sub_agents": [s.name for s in plan.sub_agents],
                "rationale": plan.rationale,
            },
            "signals": {
                "security": signals.has_security_signal,
                "performance": signals.has_perf_signal,
                "architecture": signals.has_architecture_signal,
                "test": signals.has_test_signal,
                "dependency": signals.has_dep_signal,
                "migration": signals.has_migration_signal,
                "api": signals.has_api_signal,
                "large_change": signals.is_large_change,
                "risk_indicators": signals.risk_indicators,
            },
            "findings_count": record.findings_count,
            "findings_by_severity": outcome.findings_by_severity,
            "findings": [f.model_dump(mode="json") for f in outcome.aggregated_findings],
            "sub_agent_results": [
                {
                    "name": r.agent_name,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                    "findings_count": len(r.findings),
                    "fallback_used": r.fallback_used,
                    "skills_invoked": r.skills_invoked,
                    "error": r.error,
                }
                for r in outcome.sub_agent_results
            ],
            "telemetry": {
                "duration_ms": record.duration_ms,
                "model_calls": record.model_calls,
                "estimated_cost_usd": record.estimated_cost_usd,
            },
            "run_record": record.model_dump(mode="json"),
        }

    # ─────────────────────────────────────────────────────
    # CAB Brief Generation
    # ─────────────────────────────────────────────────────
    async def generate_cab_brief(
        self,
        *,
        pr_id: int,
        repo: str,
        pr_number: int,
        title: str,
        author: str,
        branch: str,
        diff_text: str,
        findings: list[dict[str, Any]] | None = None,
        description: str = "",
        base_branch: str = "main",
    ) -> dict[str, Any]:
        new_correlation_id(prefix="cab")
        ctx = self.perception.build(
            pr_id=pr_id, repo=repo, pr_number=pr_number, title=title,
            description=description, author=author, branch=branch,
            base_branch=base_branch, diff_text=diff_text,
        )
        agent = CABDocumentAgent()
        result = await agent.execute(
            SkillContext(pr=ctx, parameters={"findings": findings or []}),
            self.model,
        )
        return {
            "ok": result.success,
            "pr_id": pr_id, "repo": repo, "pr_number": pr_number,
            "brief": (result.payload or {}).get("brief"),
            "risk_level": (result.payload or {}).get("risk_level"),
            "risk_score": (result.payload or {}).get("risk_score"),
            "fallback_used": result.fallback_used,
            "telemetry": {
                "duration_ms": result.duration_ms,
                "model_calls": result.model_calls,
                "estimated_cost_usd": result.estimated_cost_usd,
            },
            "error": result.error,
        }

    # ─────────────────────────────────────────────────────
    # Scorecard Generation
    # ─────────────────────────────────────────────────────
    async def generate_scorecard(self, *, metrics: dict[str, Any]) -> dict[str, Any]:
        new_correlation_id(prefix="scorecard")
        agent = ScorecardAgent()
        result = await agent.execute(
            SkillContext(parameters={"metrics": metrics}),
            self.model,
        )
        return {
            "ok": result.success,
            "snapshot": (result.payload or {}).get("snapshot"),
            "fallback_used": result.fallback_used,
            "telemetry": {
                "duration_ms": result.duration_ms,
                "model_calls": result.model_calls,
                "estimated_cost_usd": result.estimated_cost_usd,
            },
            "error": result.error,
        }


# Module-level convenience for callers that don't want to manage the instance
_DEFAULT_AGENT: MasterAgent | None = None


def _get() -> MasterAgent:
    global _DEFAULT_AGENT
    if _DEFAULT_AGENT is None:
        _DEFAULT_AGENT = MasterAgent()
    return _DEFAULT_AGENT


async def run_master_agent(operation: str, **kwargs: Any) -> dict[str, Any]:
    """Single dispatch helper · operation ∈ {review_pr, generate_cab_brief, generate_scorecard}."""
    agent = _get()
    method = getattr(agent, operation, None)
    if method is None:
        raise ValueError(f"Unknown operation: {operation}")
    return await method(**kwargs)
