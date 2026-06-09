"""Resource Management skill · file handles · connections · context managers.

Purpose
-------
Catches resource leaks that don't crash development but exhaust production
pools and file descriptors: `open()` without `with`, `psycopg2.connect()`
allocated bare, `ExecutorService` without shutdown.

Methodology
-----------
1. **Deterministic regex pass** — `RESOURCE_PATTERNS` from the shared catalog.
2. **LLM contextual pass** — surfaces leaks needing dataflow understanding.

Authoritative standards consulted
---------------------------------
- PEP-343 (The `with` statement)
- CWE-400 (Resource exhaustion)
- Java Concurrency in Practice (Goetz)
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import RESOURCE_PATTERNS
from skills._shared.standards import JAVA_CONCURRENCY_BOOK, PEP_343_WITH
from skills.base import Skill, register_skill

logger = get_logger(__name__)


@register_skill
class ResourceManagementSkill(Skill):
    name = "resource_management"
    description = "FD leaks · connection leaks · executor shutdown · PEP-343 grounded"
    dimensions = [Dimension.RESOURCE_MANAGEMENT.value]

    STANDARDS = [PEP_343_WITH, JAVA_CONCURRENCY_BOOK]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm: list = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You review resource hygiene. Your beat: unclosed file handles, "
                "leaked DB / HTTP connections, executors without shutdown, "
                "context managers omitted on resources that need them. Cite "
                "PEP-343 or the relevant CWE in every finding."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"Resource-management review.\n\nDiff:\n```\n{self.diff_blob(ctx, 4500)}\n```",
                skill_name=self.name, default_dimension=Dimension.RESOURCE_MANAGEMENT,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.resource.fallback", error=str(exc)[:200])
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
                for spec in RESOURCE_PATTERNS:
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
