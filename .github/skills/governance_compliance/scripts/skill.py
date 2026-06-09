"""Governance Compliance skill · naming · ownership · release rules.

Purpose
-------
Catches the governance lapses that an enterprise risk team eventually
flags as audit findings: PEP-8 / Java-naming violations, CODEOWNERS
gaps, anonymous TODOs, missing CHANGELOG.

Authoritative standards consulted
---------------------------------
- PEP 8 · Naming Conventions
- Oracle Java Language Specification · Naming
- Conventional Commits 1.0
- Semantic Versioning 2.0
- Keep a Changelog
- GitHub CODEOWNERS Documentation
- ITIL 4 · Change Enablement (release windows, approvals)
"""
from __future__ import annotations

import re

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, Severity, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.standards import (
    CWE_546_SUSPICIOUS_CMT,
    ITIL_4_CHANGE_MGMT,
    ORACLE_JAVA_NAMING,
    PEP_8_STYLE,
    SEMANTIC_VERSIONING,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)

# (rule_id, severity, languages, regex, title, why, references)
_NAMING_RULES = [
    ("naming.py_class_pascal", Severity.MINOR, {"python"},
     re.compile(r"^\+\s*class\s+([a-z][a-zA-Z0-9_]*)\s*[:\(]"),
     "Python class not PascalCase", "PEP 8: classes use CapWords.",
     [PEP_8_STYLE]),
    ("naming.py_func_snake", Severity.MINOR, {"python"},
     re.compile(r"^\+\s*def\s+([A-Z][a-zA-Z0-9_]*)\s*\("),
     "Python function not snake_case", "PEP 8: functions are lowercase with underscores.",
     [PEP_8_STYLE]),
    ("naming.java_class_pascal", Severity.MINOR, {"java", "scala", "kotlin"},
     re.compile(r"^\+\s*public\s+class\s+([a-z][a-zA-Z0-9_]*)\b"),
     "Java class not PascalCase", "Oracle Java Naming: classes use UpperCamelCase.",
     [ORACLE_JAVA_NAMING]),
    ("naming.todo_no_owner", Severity.NIT, {"python", "java", "scala", "typescript", "javascript"},
     re.compile(r"^\+.*(?:#|//)\s*TODO(?!\s*\()"),
     "TODO without owner", "Anonymous TODOs accumulate forever; reference an issue or person.",
     [CWE_546_SUSPICIOUS_CMT]),
]


@register_skill
class GovernanceComplianceSkill(Skill):
    name = "governance_compliance"
    description = "Naming · ownership · release rules · PEP-8 / Oracle Java Naming / ITIL 4 grounded"
    dimensions = [Dimension.GOVERNANCE.value]

    STANDARDS = [
        PEP_8_STYLE, ORACLE_JAVA_NAMING, SEMANTIC_VERSIONING,
        ITIL_4_CHANGE_MGMT, CWE_546_SUSPICIOUS_CMT,
    ]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You enforce organizational standards. Your beat: naming-convention violations "
                "(class/function/file/table casing), ownership gaps (file changed without "
                "CODEOWNERS coverage), release-rule violations (e.g., main-branch hotfix on "
                "weekends, deploys without freeze-window approval), CHANGELOG missing for "
                "user-facing changes. Skip findings that are security/perf/style (delegated)."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"Governance review.\n\nDiff:\n```\n{self.diff_blob(ctx, 4500)}\n```",
                skill_name=self.name, default_dimension=Dimension.GOVERNANCE,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.governance.fallback", error=str(exc)[:200])
        merged = apply_memory_adjustments(det + llm, ctx)
        for f in merged:
            f.auto_postable = f.confidence >= 75
        return SkillResult(findings=merged, fallback_used=fallback, **telemetry)

    def _deterministic(self, ctx: SkillContext) -> list:
        if ctx.pr is None:
            return []
        out = []
        for fc in ctx.pr.files:
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                for off, line in enumerate(hunk.get("lines", [])):
                    for rid, sev, langs, pat, title, why, refs in _NAMING_RULES:
                        if fc.language not in langs:
                            continue
                        if pat.search(line):
                            out.append(make_finding(
                                rule_id=rid, skill=self.name,
                                dimension=Dimension.GOVERNANCE, severity=sev,
                                confidence=82, file=fc.path, line=start + off,
                                title=title, why=why,
                                fix="Rename per the convention.",
                                quote=line.lstrip("+").strip()[:200],
                                references=refs,
                            ))
        return out
