"""SubAgent base · specialized worker invoked by MasterAgent."""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any

from Agents.Core.model import DatabricksClaude
from Agents.Core.observability import get_logger, trace_span
from Agents.Core.schemas import Finding, SkillContext

logger = get_logger(__name__)


@dataclass
class SubAgentResult:
    agent_name: str
    success: bool
    duration_ms: int
    findings: list[Finding] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    skills_invoked: list[str] = field(default_factory=list)
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    fallback_used: bool = False
    error: str | None = None


class SubAgent(abc.ABC):
    """Specialized worker · one concern per agent.

    Sub-agents own a small set of skills and a tight contract:
    given a SkillContext, produce a SubAgentResult.
    """
    name: str
    description: str

    @abc.abstractmethod
    def skills(self) -> list[str]:
        """List of skill names this sub-agent invokes."""

    async def execute(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SubAgentResult:
        t0 = time.perf_counter()
        try:
            with trace_span(f"sub_agent.{self.name}"):
                result = await self.run(ctx, model)
        except Exception as exc:
            logger.exception("sub_agent.failed", agent=self.name)
            return SubAgentResult(
                agent_name=self.name,
                success=False,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )
        result.duration_ms = int((time.perf_counter() - t0) * 1000)
        return result

    @abc.abstractmethod
    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        ...

    # ─── Convenience aggregator for skill-driven sub-agents ─
    async def _run_skills(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        from skills.base import get_skill_registry
        registry = get_skill_registry()
        findings: list[Finding] = []
        invoked: list[str] = []
        cost = mc = it = ot = 0
        fallback_seen = False
        cost_f = 0.0
        for sname in self.skills():
            skill = registry.get(sname)
            if skill is None:
                continue
            if not skill.should_run(ctx):
                continue
            result = await skill.execute(ctx, model)
            findings.extend(result.findings)
            invoked.append(sname)
            mc += result.model_calls
            it += result.input_tokens
            ot += result.output_tokens
            cost_f += result.estimated_cost_usd
            fallback_seen = fallback_seen or result.fallback_used
        return SubAgentResult(
            agent_name=self.name,
            success=True,
            duration_ms=0,            # set by execute()
            findings=findings,
            skills_invoked=invoked,
            model_calls=mc,
            input_tokens=it,
            output_tokens=ot,
            estimated_cost_usd=round(cost_f, 6),
            fallback_used=fallback_seen,
        )
