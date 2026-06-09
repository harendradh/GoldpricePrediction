"""Architecture SubAgent · layer integrity + API contract + data model."""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.schemas import SkillContext
from Agents.SubAgents.base import SubAgent, SubAgentResult


class ArchitectureAgent(SubAgent):
    name = "architecture_agent"
    description = "Layer integrity + public API contracts + DB schema migrations"

    def skills(self) -> list[str]:
        return [
            "architecture_validation",
            "api_contract_validation",
            "database_migration",
        ]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        return await self._run_skills(ctx, model)
