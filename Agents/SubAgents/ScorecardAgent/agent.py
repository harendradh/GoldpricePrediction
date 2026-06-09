"""Scorecard SubAgent · narrates per-team metrics."""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.schemas import ScorecardMetrics, ScorecardSnapshot, SkillContext
from skills.base import get_skill_registry
from Agents.SubAgents.base import SubAgent, SubAgentResult


class ScorecardAgent(SubAgent):
    name = "scorecard_agent"
    description = "Generates per-team scorecard snapshot · narrative · grade · risk signals"

    def skills(self) -> list[str]:
        return ["scorecard_narration"]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        metrics_raw = ctx.parameters.get("metrics")
        if metrics_raw is None:
            return SubAgentResult(
                agent_name=self.name, success=False, duration_ms=0,
                error="missing parameters.metrics",
            )
        metrics = ScorecardMetrics(**metrics_raw) if not isinstance(metrics_raw, ScorecardMetrics) else metrics_raw

        narration = get_skill_registry().get("scorecard_narration")
        r = await narration.execute(SkillContext(parameters={"metrics": metrics}), model)
        payload = r.payload or {}

        snapshot = ScorecardSnapshot(
            metrics=metrics,
            narrative_markdown=payload.get("narrative_markdown", ""),
            health_grade=payload.get("grade", "C"),
            risk_signals=payload.get("risk_signals", []),
            recommended_actions=payload.get("recommended_actions", []),
        )
        return SubAgentResult(
            agent_name=self.name,
            success=True,
            duration_ms=0,
            payload={"snapshot": snapshot.model_dump(mode="json")},
            skills_invoked=["scorecard_narration"],
            model_calls=r.model_calls, input_tokens=r.input_tokens,
            output_tokens=r.output_tokens, estimated_cost_usd=r.estimated_cost_usd,
            fallback_used=r.fallback_used,
        )
