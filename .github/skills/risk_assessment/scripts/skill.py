"""Risk Assessment skill · probability × impact × detectability scoring.

Purpose
-------
Quantifies change risk from finding-counts + blast-radius signals
(files_changed, additions+deletions) into a CAB-grade risk level and a
risk score. Deterministic-only — no model needed.

Methodology
-----------
1. Count BLOCKER + MAJOR findings.
2. Combine with PR shape (size + spread).
3. Map to {LOW, MEDIUM, HIGH, CRITICAL} per ITIL 4 change classification.
4. Compute risk_score = (probability × impact) / detectability for
   ordering across the portfolio.

Authoritative standards consulted
---------------------------------
- ITIL 4 · Change Enablement (risk-categorization guidance)
- NIST CSF 2.0 · ID.RA (Risk Assessment)
- Google SRE Book · Postmortem Culture (impact heuristics)
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude
from Agents.Core.observability import get_logger
from Agents.Core.schemas import CABRiskLevel, Severity, SkillContext, SkillResult
from skills._shared.standards import GOOGLE_SRE_BOOK, ITIL_4_CHANGE_MGMT, NIST_CSF_2
from skills.base import Skill, register_skill

logger = get_logger(__name__)


@register_skill
class RiskAssessmentSkill(Skill):
    name = "risk_assessment"
    description = "Quantifies change risk: probability × impact × detectability · ITIL 4 / NIST CSF grounded"
    dimensions = ["governance"]

    STANDARDS = [ITIL_4_CHANGE_MGMT, NIST_CSF_2, GOOGLE_SRE_BOOK]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        findings = ctx.parameters.get("findings", [])
        pr = ctx.pr

        blockers = sum(1 for f in findings if (
            f.severity == Severity.BLOCKER if hasattr(f, "severity")
            else str(f.get("severity", "")).upper() == "BLOCKER"
        ))
        majors = sum(1 for f in findings if (
            f.severity == Severity.MAJOR if hasattr(f, "severity")
            else str(f.get("severity", "")).upper() == "MAJOR"
        ))
        big_diff = pr is not None and (pr.total_additions + pr.total_deletions) > 500
        many_files = pr is not None and pr.files_changed > 10

        if blockers:
            level = CABRiskLevel.HIGH
        elif majors and big_diff:
            level = CABRiskLevel.HIGH
        elif majors or big_diff:
            level = CABRiskLevel.MEDIUM
        else:
            level = CABRiskLevel.LOW

        probability = 0.4 if blockers else (0.25 if majors else 0.1)
        impact = 0.6 if many_files else (0.4 if majors else 0.2)
        detectability = 0.85  # assume good monitoring baseline
        risk_score = round(probability * impact * (1 / detectability), 4)

        return SkillResult(payload={
            "risk_level": level.value,
            "probability": probability,
            "impact": impact,
            "detectability": detectability,
            "risk_score": risk_score,
            "blocker_count": blockers,
            "major_count": majors,
        })
