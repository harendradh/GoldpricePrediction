"""Concurrency Analysis skill · races · async hygiene · thread safety.

Purpose
-------
Catches concurrency footguns that surface as production flakes weeks later:
blocking calls inside `async def`, double-checked locking without `volatile`,
unnamed threads, mutable globals shared across workers.

Methodology
-----------
1. **Deterministic regex pass** — `CONCURRENCY_PATTERNS` in
   `_shared/patterns.py`.
2. **LLM contextual pass** — race conditions that only show with knowledge
   of how the threads share state.

Authoritative standards consulted
---------------------------------
- Java Concurrency in Practice (Goetz)
- PEP-492 (Coroutines via async/await)
- Python asyncio docs · Best Practices
- Effective Java Items on concurrency
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import CONCURRENCY_PATTERNS
from skills._shared.standards import (
    JAVA_CONCURRENCY_BOOK,
    PEP_492_ASYNCIO,
    PYTHON_ASYNCIO_BEST,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)


@register_skill
class ConcurrencyAnalysisSkill(Skill):
    name = "concurrency_analysis"
    description = "Race conditions · async hygiene · thread safety · Java Concurrency / PEP-492 grounded"
    dimensions = [Dimension.CONCURRENCY.value]

    STANDARDS = [JAVA_CONCURRENCY_BOOK, PEP_492_ASYNCIO, PYTHON_ASYNCIO_BEST]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm: list = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You review concurrency and async patterns. Your beat: "
                "blocking calls inside async functions, double-checked locking "
                "without `volatile`, anonymous threads, mutable globals shared "
                "across workers, missing locks on shared state, asyncio gather "
                "without exception handling. Cite Java Concurrency in Practice "
                "or PEP-492 in every finding."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"Concurrency review.\n\nDiff:\n```\n{self.diff_blob(ctx, 4500)}\n```",
                skill_name=self.name, default_dimension=Dimension.CONCURRENCY,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.concurrency.fallback", error=str(exc)[:200])
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
                for spec in CONCURRENCY_PATTERNS:
                    if spec.regex.search(text):
                        loc, quote = start, text[:120]
                        for off, ln in enumerate(hunk.get("lines", [])):
                            if spec.regex.search(ln):
                                loc, quote = start + off, ln.lstrip("+").strip()
                                break
                        out.append(make_finding(
                            rule_id=spec.rule_id, skill=self.name,
                            dimension=spec.dimension, severity=spec.severity,
                            confidence=84, file=fc.path, line=loc,
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
