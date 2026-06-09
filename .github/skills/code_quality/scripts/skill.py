"""Code Quality skill · idiom · maintainability · style · simple correctness bugs.

Purpose
-------
Catches the bugs and anti-patterns that a senior reviewer would flag on first read.
Stays in the "is this code well-written" lane and explicitly does NOT cover
security (delegated to `security_scan`), performance (`performance_analysis`),
or architecture (`architecture_validation`).

Methodology
-----------
Two-pass detection:

1. **Deterministic regex pass** — runs first, in-process, no network. Matches
   high-precision patterns drawn from PEP 8, Effective Python, Effective Java,
   and the Python docs' "Common Pitfalls" sections. Findings carry
   confidence ≥ 80 because the patterns are vetted for low false-positive rate.

2. **LLM contextual pass** — runs only if the model is reachable. The model is
   given the diff + the locked standards catalog (PEP-8, PEP-257, Google
   Python Style Guide, Clean Code) and asked to surface issues the regex pass
   can't see (subtle naming problems, complexity that doesn't trip a pattern,
   missing edge-case handling).

Outputs are merged + deduped on (rule_id, file, line). Memory adjustments
(per-repo confidence tuning from past triage decisions) are applied before
returning, then `auto_postable` is flagged if confidence ≥ 80.

Authoritative standards consulted
---------------------------------
- PEP 8 — Style Guide for Python Code        https://peps.python.org/pep-0008/
- PEP 20 — The Zen of Python                 https://peps.python.org/pep-0020/
- PEP 257 — Docstring Conventions            https://peps.python.org/pep-0257/
- PEP 484 — Type Hints                       https://peps.python.org/pep-0484/
- Google Python Style Guide                  https://google.github.io/styleguide/pyguide.html
- Effective Java 3rd Edition (Bloch)         https://www.oreilly.com/library/view/effective-java/9780134686097/
- Clean Code (Robert C. Martin)              https://www.oreilly.com/library/view/clean-code/9780136083238/

What this skill catches
-----------------------
- Bare `except:` clauses → CWE-703, PEP-8
- Mutable default arguments → classic Python footgun (PEP-8, Google Python Style)
- `assert` used as runtime validation → fails under `python -O`
- `print()` instead of structured logging → unobservable in prod
- Silent exception swallowing → CWE-703
- Java `Optional.get()` without check → defeats Optional (Effective Java Item 55)
- Java `String.equals()` with possibly-null lhs → NPE (Effective Java Item 55)
- `new BigDecimal(double)` → IEEE-754 precision loss

What this skill explicitly does NOT catch
-----------------------------------------
- Security holes → `security_scan` owns those
- Performance regressions → `performance_analysis`
- Layer violations → `architecture_validation`
- Missing tests → `test_coverage_analysis`
- Dependency drift → `dependency_audit`
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import CORRECTNESS_JAVA, CORRECTNESS_PY
from skills._shared.standards import (
    CLEAN_CODE,
    EFFECTIVE_JAVA_55,
    EFFECTIVE_JAVA_77,
    GOOGLE_JAVA_STYLE,
    GOOGLE_PYTHON_STYLE,
    PEP_8_STYLE,
    PEP_257_DOCSTRINGS,
    PEP_484_TYPE_HINTS,
    PYTHON_LOGGING_BEST,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)


@register_skill
class CodeQualitySkill(Skill):
    name = "code_quality"
    description = "Idiom · maintainability · style · simple correctness bugs · PEP-8 / Effective Java grounded"
    dimensions = [Dimension.CORRECTNESS.value, Dimension.DOCUMENTATION.value]

    # Authoritative references inlined into the LLM prompt
    STANDARDS = [
        PEP_8_STYLE, PEP_257_DOCSTRINGS, PEP_484_TYPE_HINTS,
        GOOGLE_PYTHON_STYLE, GOOGLE_JAVA_STYLE,
        EFFECTIVE_JAVA_55, EFFECTIVE_JAVA_77,
        CLEAN_CODE, PYTHON_LOGGING_BEST,
    ]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm_findings: list = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You are a senior code reviewer specializing in idiom, "
                "maintainability, and simple correctness bugs. Catch the things "
                "a strong reviewer would flag on first read: long functions, "
                "naming smells, missing type hints on public APIs, subtle null / "
                "empty-handling bugs, error-handling smells, dead code.\n\n"
                "Stay in your lane — skip security (delegated to security_scan), "
                "performance (performance_analysis), architecture "
                "(architecture_validation), and dependency hygiene "
                "(dependency_audit). Cite the specific standard you're applying "
                "(PEP-8 section, Effective Java item, Clean Code rule) in every "
                "finding's `references` array."
            )
            usr_p = self._user_prompt(ctx)
            llm_findings, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p, user_prompt=usr_p,
                skill_name=self.name, default_dimension=Dimension.CORRECTNESS,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.code_quality.fallback", error=str(exc)[:200])
        merged = apply_memory_adjustments(self._dedupe(det + llm_findings), ctx)
        for f in merged:
            f.auto_postable = f.confidence >= 80
        return SkillResult(
            findings=merged,
            payload={"deterministic": len(det), "llm": len(llm_findings)},
            fallback_used=fallback,
            **telemetry,
        )

    def _user_prompt(self, ctx: SkillContext) -> str:
        title = ctx.pr.title if ctx.pr else "n/a"
        return (
            f"PR title: {title}\n\n"
            "Review the diff for code-quality issues. Every finding must cite "
            "at least one authoritative standard in its `references` field — "
            "no opinions without grounding.\n\n"
            f"Diff:\n```\n{self.diff_blob(ctx, 5500)}\n```"
        )

    def _deterministic(self, ctx: SkillContext) -> list:
        """Pattern-based catches · precision-tuned, no LLM dependency."""
        if ctx.pr is None:
            return []
        out = []
        for fc in ctx.pr.files:
            patterns = CORRECTNESS_PY if fc.language == "python" else (
                CORRECTNESS_JAVA if fc.language in {"java", "scala", "kotlin"} else []
            )
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                for off, line in enumerate(hunk.get("lines", [])):
                    for spec in patterns:
                        if spec.regex.search(line):
                            out.append(make_finding(
                                rule_id=spec.rule_id,
                                skill=self.name,
                                dimension=spec.dimension,
                                severity=spec.severity,
                                confidence=85,
                                file=fc.path,
                                line=start + off,
                                title=spec.title,
                                why=spec.why,
                                fix=spec.fix,
                                quote=line.lstrip("+").strip()[:200],
                                references=spec.references,
                            ))
        return out

    @staticmethod
    def _dedupe(findings):
        seen = set()
        out = []
        for f in findings:
            k = (f.rule_id, f.file, f.line_start)
            if k not in seen:
                seen.add(k)
                out.append(f)
        return out
