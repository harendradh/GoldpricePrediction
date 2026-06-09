"""Dependency Audit skill · supply chain · CVE detection · pin hygiene.

Purpose
-------
Catches the supply-chain anti-patterns that NIST SP 800-218 SSDF and SLSA
explicitly forbid: unpinned versions, git URLs on mutable branches,
wildcards. These are the leaks that turn a Friday upstream release into a
Monday outage.

Methodology
-----------
1. **Deterministic regex pass** — `DEPENDENCY_PATTERNS` runs on
   requirements files (requirements*.txt, pyproject.toml, package.json,
   pom.xml). Three precision rules with NIST/SLSA citations.
2. **LLM contextual pass** — surfaces ecosystem-specific oversights and
   CVE-fame packages.

Authoritative standards consulted
---------------------------------
- NIST SP 800-218 SSDF (Secure Software Development Framework)
- OWASP A06:2021 — Vulnerable and Outdated Components
- OWASP Dependency Cheat Sheet
- SLSA Supply-chain Levels for Software Artifacts
- Semantic Versioning 2.0
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import DEPENDENCY_PATTERNS
from skills._shared.standards import (
    NIST_SP_800_218_SSDF,
    OWASP_A06_VULN_COMPONENTS,
    OWASP_CHEAT_DEPENDENCY,
    SEMANTIC_VERSIONING,
    SLSA_FRAMEWORK,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)

_DEP_FILES = (
    "requirements.txt", "requirements-",
    "pyproject.toml", "package.json", "package-lock.json",
    "pom.xml", "build.gradle", "go.mod", "Cargo.toml",
)


@register_skill
class DependencyAuditSkill(Skill):
    name = "dependency_audit"
    description = "Supply chain · pin hygiene · CVE risk · NIST 800-218 SSDF / SLSA grounded"
    dimensions = [Dimension.DEPENDENCIES.value, Dimension.SECURITY.value]

    STANDARDS = [
        NIST_SP_800_218_SSDF, OWASP_A06_VULN_COMPONENTS, OWASP_CHEAT_DEPENDENCY,
        SLSA_FRAMEWORK, SEMANTIC_VERSIONING,
    ]

    def should_run(self, ctx: SkillContext) -> bool:
        if ctx.pr is None:
            return False
        return any(any(h in f.path for h in _DEP_FILES) for f in ctx.pr.files)

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm: list = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You audit dependency changes for supply-chain hygiene. Your "
                "beat: unpinned versions, mutable git URLs (branch refs), "
                "wildcard versions, known CVE-fame packages, missing lockfile "
                "updates. Cite NIST SP 800-218 SSDF or OWASP A06 in every "
                "finding."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"Dependency audit.\n\nDiff:\n```\n{self.diff_blob(ctx, 4500)}\n```",
                skill_name=self.name, default_dimension=Dimension.DEPENDENCIES,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.dep_audit.fallback", error=str(exc)[:200])
        merged = apply_memory_adjustments(self._dedupe(det + llm), ctx)
        for f in merged:
            f.auto_postable = f.confidence >= 75
        return SkillResult(findings=merged, fallback_used=fallback, **telemetry,
                           payload={"deterministic": len(det), "llm": len(llm)})

    def _deterministic(self, ctx: SkillContext) -> list:
        if ctx.pr is None:
            return []
        out = []
        for fc in ctx.pr.files:
            if not any(h in fc.path for h in _DEP_FILES):
                continue
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                text = "\n".join(hunk.get("lines", []))
                for spec in DEPENDENCY_PATTERNS:
                    if spec.regex.search(text):
                        loc, quote = start, text[:120]
                        for off, ln in enumerate(hunk.get("lines", [])):
                            if spec.regex.search(ln):
                                loc, quote = start + off, ln.lstrip("+").strip()
                                break
                        out.append(make_finding(
                            rule_id=spec.rule_id, skill=self.name,
                            dimension=spec.dimension, severity=spec.severity,
                            confidence=82, file=fc.path, line=loc,
                            title=spec.title, why=spec.why, fix=spec.fix,
                            quote=quote[:200], references=spec.references,
                        ))
        return out

    @staticmethod
    def _dedupe(findings):
        seen = set(); out = []
        for f in findings:
            k = (f.rule_id, f.file, f.line_start)
            if k not in seen:
                seen.add(k); out.append(f)
        return out
