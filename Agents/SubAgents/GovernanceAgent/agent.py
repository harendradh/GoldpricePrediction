"""Governance SubAgent · naming · ownership · release rules."""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.schemas import SkillContext
from Agents.SubAgents.base import SubAgent, SubAgentResult


class GovernanceAgent(SubAgent):
    name = "governance_agent"
    description = "Naming · ownership · release rules · enterprise standards"

    def skills(self) -> list[str]:
        return ["governance_compliance"]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        return await self._run_skills(ctx, model)
