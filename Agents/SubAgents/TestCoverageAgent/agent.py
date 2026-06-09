"""Test Coverage SubAgent · standalone test-quality analysis."""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.schemas import SkillContext
from Agents.SubAgents.base import SubAgent, SubAgentResult


class TestCoverageAgent(SubAgent):
    name = "test_coverage_agent"
    description = "Test gaps + assertion quality + brittleness"

    def skills(self) -> list[str]:
        return ["test_coverage_analysis"]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        return await self._run_skills(ctx, model)
