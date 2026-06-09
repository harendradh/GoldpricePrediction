"""Performance Review SubAgent · Spark + O(n²) + I/O + concurrency + resources."""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.schemas import SkillContext
from Agents.SubAgents.base import SubAgent, SubAgentResult


class PerformanceReviewAgent(SubAgent):
    name = "performance_review_agent"
    description = "Performance + concurrency + resource management"

    def skills(self) -> list[str]:
        return [
            "performance_analysis",
            "concurrency_analysis",
            "resource_management",
        ]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        return await self._run_skills(ctx, model)
