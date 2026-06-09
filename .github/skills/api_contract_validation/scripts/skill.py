"""API Contract Validation skill · breaking changes · OpenAPI / GraphQL / RFC-7807.

Purpose
-------
Catches the contract changes that break consumers without anyone noticing
until tickets pour in: removed response fields, narrowed types
(`nullable: true` → `false`), error responses missing the RFC-7807 envelope.

Methodology
-----------
1. **Deterministic regex pass** — `API_PATTERNS` on OpenAPI / GraphQL
   schema files. Three BLOCKER/MINOR rules.
2. **LLM contextual pass** — surfaces consumer-impact issues a regex
   can't see (semantic narrowing of a field's allowed values, etc.).

Authoritative standards consulted
---------------------------------
- OpenAPI Specification 3.1
- Semantic Versioning 2.0
- RFC 7807 (Problem Details for HTTP APIs)
- Stripe API Versioning Strategy
- GraphQL Schema Versioning Best Practices
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import API_PATTERNS
from skills._shared.standards import (
    OPENAPI_3_1,
    RFC_7807_PROBLEM,
    SEMANTIC_VERSIONING,
    STRIPE_API_VERSIONING,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)

_API_HINTS = (
    "openapi.yaml", "openapi.yml", "openapi.json",
    "swagger.yaml", "swagger.yml", "swagger.json",
    "/schema.graphql", ".graphql", "/api/",
)


@register_skill
class ApiContractValidationSkill(Skill):
    name = "api_contract_validation"
    description = "Breaking API changes · OpenAPI / GraphQL / RFC-7807 grounded"
    dimensions = [Dimension.API_CONTRACT.value, Dimension.ARCHITECTURE.value]

    STANDARDS = [OPENAPI_3_1, SEMANTIC_VERSIONING, RFC_7807_PROBLEM, STRIPE_API_VERSIONING]

    def should_run(self, ctx: SkillContext) -> bool:
        if ctx.pr is None:
            return False
        return any(any(h in f.path.lower() for h in _API_HINTS) for f in ctx.pr.files)

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm: list = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You audit API contract changes. Your beat: removed fields, "
                "narrowed types, breaking renames, error responses missing "
                "the RFC-7807 envelope, missing deprecation warm-up. Cite "
                "OpenAPI 3.1, RFC 7807, or Semantic Versioning in every finding."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"API contract review.\n\nDiff:\n```\n{self.diff_blob(ctx, 4500)}\n```",
                skill_name=self.name, default_dimension=Dimension.API_CONTRACT,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.api_contract.fallback", error=str(exc)[:200])
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
            if not any(h in fc.path.lower() for h in _API_HINTS):
                continue
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                text = "\n".join(hunk.get("lines", []))
                for spec in API_PATTERNS:
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
