"""Dependency Audit SubAgent · supply-chain + CVE detection."""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.schemas import SkillContext
from Agents.SubAgents.base import SubAgent, SubAgentResult


class DependencyAuditAgent(SubAgent):
    name = "dependency_audit_agent"
    description = "Supply chain · CVE · pin hygiene"

    def skills(self) -> list[str]:
        return ["dependency_audit"]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        return await self._run_skills(ctx, model)
