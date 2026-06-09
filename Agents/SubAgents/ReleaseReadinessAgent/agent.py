"""Release Readiness SubAgent · aggregates findings into READY / NOT READY verdict + score."""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.schemas import Severity, SkillContext
from Agents.SubAgents.base import SubAgent, SubAgentResult


class ReleaseReadinessAgent(SubAgent):
    name = "release_readiness_agent"
    description = "Aggregates findings + decisions into ready / not_ready verdict + risk score"

    def skills(self) -> list[str]:
        return ["risk_assessment"]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        findings = ctx.parameters.get("findings", [])
        unresolved_blockers = [f for f in findings if (
            (f.severity == Severity.BLOCKER if hasattr(f, "severity")
             else str(f.get("severity", "")).upper() == "BLOCKER")
            and not (hasattr(f, "decision") and getattr(f, "decision", None) == "dismiss")
        )]
        unresolved_majors = [f for f in findings if (
            (f.severity == Severity.MAJOR if hasattr(f, "severity")
             else str(f.get("severity", "")).upper() == "MAJOR")
            and not getattr(f, "decision", None)
        )]
        if unresolved_blockers:
            verdict = "not_ready"
        elif unresolved_majors:
            verdict = "ready_with_conditions"
        else:
            verdict = "ready"

        # Compute risk score (mirrors RiskAssessmentSkill formula)
        risk_score = round(
            min(100, 20 * len(unresolved_blockers) + 5 * len(unresolved_majors) + 2),
            2,
        )

        return SubAgentResult(
            agent_name=self.name,
            success=True,
            duration_ms=0,
            payload={
                "verdict": verdict,
                "risk_score": risk_score,
                "unresolved_blockers": len(unresolved_blockers),
                "unresolved_majors": len(unresolved_majors),
            },
        )
