"""Database Migration skill · schema-change risk · zero-downtime patterns.

Purpose
-------
Catches the migrations that take prod offline: `ADD COLUMN NOT NULL`
without default (table rewrite under exclusive lock), `DROP COLUMN`
before the read-side stops referencing it, `RENAME COLUMN` (atomic
breakage), `CREATE INDEX` without `CONCURRENTLY`.

Methodology
-----------
1. **Deterministic regex pass** — `DB_MIGRATION_PATTERNS` from the shared
   catalog. Four BLOCKER/MAJOR rules grounded in PG docs + expand/contract.
2. **LLM contextual pass** — looks at the broader migration narrative
   (does the diff include the matching app-code change? is there a
   backfill script?).

Authoritative standards consulted
---------------------------------
- PostgreSQL Documentation · DDL Locking
- PostgreSQL Wiki · Lock-friendly Schema Updates
- Liquibase Best Practices
- Alembic Cookbook
- Expand/Contract pattern (PragDave / Sam Newman)
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import DB_MIGRATION_PATTERNS
from skills._shared.standards import (
    EXPAND_CONTRACT,
    PG_DOC_DDL,
    PG_LOCKING_BEST,
    ZERO_DOWNTIME_MIGRATION,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)

_MIGRATION_HINTS = (
    "/migration", "/migrations/", "/alembic/", "/liquibase/",
    "/db/migrate/", "schema.sql", ".sql",
)


@register_skill
class DatabaseMigrationSkill(Skill):
    name = "database_migration"
    description = "Schema-change risk · backwards compat · expand/contract grounded"
    dimensions = [Dimension.DATA_MODEL.value]

    STANDARDS = [PG_DOC_DDL, PG_LOCKING_BEST, ZERO_DOWNTIME_MIGRATION, EXPAND_CONTRACT]

    def should_run(self, ctx: SkillContext) -> bool:
        if ctx.pr is None:
            return False
        return any(any(h in f.path.lower() for h in _MIGRATION_HINTS) for f in ctx.pr.files)

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm: list = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You review database migrations for zero-downtime safety. Your "
                "beat: locking semantics, backfill plans, expand/contract "
                "phasing, rollback path. Cite PostgreSQL DDL docs or the "
                "expand/contract pattern in every finding."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"Migration review.\n\nDiff:\n```\n{self.diff_blob(ctx, 4500)}\n```",
                skill_name=self.name, default_dimension=Dimension.DATA_MODEL,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.db_migration.fallback", error=str(exc)[:200])
        merged = apply_memory_adjustments(self._dedupe(det + llm), ctx)
        for f in merged:
            f.auto_postable = f.confidence >= 80
        return SkillResult(findings=merged, fallback_used=fallback, **telemetry,
                           payload={"deterministic": len(det), "llm": len(llm)})

    def _deterministic(self, ctx: SkillContext) -> list:
        if ctx.pr is None:
            return []
        out = []
        for fc in ctx.pr.files:
            if not any(h in fc.path.lower() for h in _MIGRATION_HINTS):
                continue
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                text = "\n".join(hunk.get("lines", []))
                for spec in DB_MIGRATION_PATTERNS:
                    if spec.regex.search(text):
                        loc, quote = start, text[:120]
                        for off, ln in enumerate(hunk.get("lines", [])):
                            if spec.regex.search(ln):
                                loc, quote = start + off, ln.lstrip("+").strip()
                                break
                        out.append(make_finding(
                            rule_id=spec.rule_id, skill=self.name,
                            dimension=spec.dimension, severity=spec.severity,
                            confidence=88, file=fc.path, line=loc,
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
