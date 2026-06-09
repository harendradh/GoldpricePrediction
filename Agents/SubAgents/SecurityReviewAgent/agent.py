"""Security Review SubAgent · injection + secrets + crypto + PII + dep CVEs + config."""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.schemas import SkillContext
from Agents.SubAgents.base import SubAgent, SubAgentResult


class SecurityReviewAgent(SubAgent):
    name = "security_review_agent"
    description = "Security lens · highest-stakes findings · always runs"

    def skills(self) -> list[str]:
        return [
            "security_scan",
            "dependency_audit",
            "configuration_validation",
        ]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        return await self._run_skills(ctx, model)
