"""Error Handling skill · exception hygiene · logging · graceful degradation.

Purpose
-------
Catches the resilience smells a senior reviewer would flag immediately:
bare except, swallowed exceptions, `printStackTrace()`, raise-without-`from`,
catching `Throwable`. Each catch ships with an OWASP / CWE / Effective-Java
reference so the engineer can verify externally.

Methodology
-----------
1. **Deterministic regex pass** — `ERROR_HANDLING_PATTERNS` in
   `_shared/patterns.py`. Five precision-tuned rules, all with citations.
2. **LLM contextual pass** — surfaces issues the regex can't see (retry
   without backoff, missing circuit breaker, wrong log level).

Authoritative standards consulted
---------------------------------
- CWE-703 (Improper Check of Exceptional Conditions)
- CWE-209 (Information Exposure Through Error Messages)
- PEP-3134 (Exception Chaining via `raise X from e`)
- PEP-8 §Programming Recommendations
- Effective Java Items 69, 73, 77
- Google SRE Book (Embracing Failure)
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import ERROR_HANDLING_PATTERNS
from skills._shared.standards import (
    CWE_209_ERROR_EXPOSURE,
    CWE_703_EXCEPTION_CHECK,
    EFFECTIVE_JAVA_69,
    EFFECTIVE_JAVA_73,
    EFFECTIVE_JAVA_77,
    GOOGLE_SRE_BOOK,
    PEP_3134_EXCEPTION,
    PEP_8_STYLE,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)


@register_skill
class ErrorHandlingReviewSkill(Skill):
    name = "error_handling_review"
    description = "Exception hygiene · logging discipline · retry / circuit-breaker · Effective-Java grounded"
    dimensions = [Dimension.ERROR_HANDLING.value]

    STANDARDS = [
        CWE_703_EXCEPTION_CHECK, CWE_209_ERROR_EXPOSURE,
        PEP_3134_EXCEPTION, PEP_8_STYLE,
        EFFECTIVE_JAVA_69, EFFECTIVE_JAVA_73, EFFECTIVE_JAVA_77,
        GOOGLE_SRE_BOOK,
    ]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm: list = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You review error-handling and resilience patterns. Your beat: "
                "untyped exceptions, swallowed exceptions, retries without "
                "backoff, missing circuit breakers on external calls, logging "
                "at the wrong level, missing error-path tests, lost exception "
                "context (raise without `from e` per PEP-3134).\n\n"
                "Cite Effective Java Items 69/73/77, PEP-3134, or the Google "
                "SRE Book in every finding."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"Error-handling review.\n\nDiff:\n```\n{self.diff_blob(ctx, 4500)}\n```",
                skill_name=self.name, default_dimension=Dimension.ERROR_HANDLING,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.err_handling.fallback", error=str(exc)[:200])
        merged = apply_memory_adjustments(self._dedupe(det + llm), ctx)
        for f in merged:
            f.auto_postable = f.confidence >= 78
        return SkillResult(findings=merged, fallback_used=fallback, **telemetry,
                           payload={"deterministic": len(det), "llm": len(llm)})

    def _deterministic(self, ctx: SkillContext) -> list:
        if ctx.pr is None:
            return []
        out = []
        for fc in ctx.pr.files:
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                text = "\n".join(hunk.get("lines", []))
                for spec in ERROR_HANDLING_PATTERNS:
                    if spec.regex.search(text):
                        loc, quote = start, text[:120]
                        for off, ln in enumerate(hunk.get("lines", [])):
                            if spec.regex.search(ln):
                                loc, quote = start + off, ln.lstrip("+").strip()
                                break
                        out.append(make_finding(
                            rule_id=spec.rule_id, skill=self.name,
                            dimension=spec.dimension, severity=spec.severity,
                            confidence=85, file=fc.path, line=loc,
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
