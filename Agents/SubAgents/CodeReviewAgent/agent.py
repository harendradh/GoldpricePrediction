"""Code Review SubAgent · correctness + style + error handling + docs + tests."""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.schemas import SkillContext
from Agents.SubAgents.base import SubAgent, SubAgentResult


class CodeReviewAgent(SubAgent):
    name = "code_review_agent"
    description = "Correctness · idiom · error handling · docs · test coverage gaps"

    def skills(self) -> list[str]:
        return [
            "code_quality",
            "error_handling_review",
            "documentation_quality",
            "test_coverage_analysis",
        ]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        return await self._run_skills(ctx, model)
