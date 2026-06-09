"""Performance Analysis skill · Spark · O(n²) · I/O · UDF cost · memory.

Purpose
-------
Catches performance regressions that would cost cluster time, drive up the
Databricks bill, or slow the nightly job from minutes to hours.

Methodology
-----------
1. **Deterministic heuristic pass** matches anti-patterns drawn from the
   Apache Spark Performance Tuning Guide and Databricks Best Practices:
   unbounded collect/toPandas, coalesce(1) in hot paths, withColumn in
   loops (O(N²) plan blowup), implicit cross joins, requests without
   timeout, string-concat-in-loop.

2. **LLM contextual pass** surfaces issues that need code understanding:
   skew after repartition, UDF where native exists, shuffle hazards on
   join keys with non-uniform distribution, missing partitionBy on big
   writes, single-partition windowing.

When citing consequences, the LLM is prompted to quantify ("scans 50M
rows per row → 12h job becomes 8d"). Bare "this is slow" is not allowed.

Authoritative standards consulted
---------------------------------
- Apache Spark Tuning Guide            https://spark.apache.org/docs/latest/tuning.html
- Spark SQL Performance Tuning         https://spark.apache.org/docs/latest/sql-performance-tuning.html
- Databricks Best Practices            https://docs.databricks.com/en/best-practices.html
- Java Performance (Oaks)              https://www.oreilly.com/library/view/java-performance-the/9781449363512/
- High Performance Python              https://www.oreilly.com/library/view/high-performance-python/9781449361747/
- Python Performance Tips (CPython)    https://wiki.python.org/moin/PythonSpeed/PerformanceTips

What this skill catches
-----------------------
Spark / PySpark:
- `df.collect()` / `df.toPandas()` unbounded → driver OOM
- `coalesce(1)` / `repartition(1)` in hot path → single-executor bottleneck
- `withColumn()` inside Python loop → O(N²) plan construction
- Implicit cross-join (`.join(other)` without `on=`)
- Cache without matching unpersist (memory leak across jobs)
- UDF used where native function exists
- Single-partition window functions (`Window.partitionBy()` missing)

Python:
- `requests.*` without timeout → blocks event loop
- String concatenation in loop → O(N²)
- Synchronous I/O inside `async def`
- `re.compile()` inside hot loop

SQL:
- Cartesian join (`FROM a, b` without WHERE)
- DELETE / UPDATE without WHERE
- `SELECT *` in views (downstream breakage)

What this skill explicitly does NOT catch
-----------------------------------------
- Memory leaks → `resource_management`
- Concurrency races → `concurrency_analysis`
- Database schema-change risks → `database_migration`
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import PERFORMANCE_PY, PERFORMANCE_SPARK, SQL_PATTERNS
from skills._shared.standards import (
    DATABRICKS_BEST,
    HIGH_PERF_PYTHON,
    JVM_PERF_BOOK,
    PYTHON_PERF_TIPS,
    SPARK_SQL_PERF_GUIDE,
    SPARK_TUNING_GUIDE,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)

_PERF_LANGS = {"python", "scala", "java", "sql", "kotlin"}


@register_skill
class PerformanceAnalysisSkill(Skill):
    name = "performance_analysis"
    description = "Performance lens · Spark / O(n²) / I/O / memory / UDF cost · grounded in Spark Tuning Guide"
    dimensions = [Dimension.PERFORMANCE.value]

    STANDARDS = [
        SPARK_TUNING_GUIDE, SPARK_SQL_PERF_GUIDE, DATABRICKS_BEST,
        JVM_PERF_BOOK, HIGH_PERF_PYTHON, PYTHON_PERF_TIPS,
    ]

    def should_run(self, ctx: SkillContext) -> bool:
        if ctx.pr is None:
            return False
        return bool(_PERF_LANGS.intersection(ctx.pr.languages_detected))

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You are a senior performance engineer with deep Spark/PySpark, "
                "JVM, and Python optimization expertise. Your beat: shuffle "
                "hazards, missing broadcast hints, unbounded collect/toPandas, "
                "UDFs where native equivalents exist, O(n²) algorithmic patterns, "
                "missing partitionBy on writes, single-partition window functions, "
                "repeated re.compile in loops, requests without timeout, "
                "synchronous I/O in async paths.\n\n"
                "Quantify the consequence in every finding ('scans 50M rows per "
                "row → 12h job becomes 8d'). 'This is slow' is not acceptable. "
                "Every finding must cite the Spark Tuning Guide, Databricks Best "
                "Practices, or one of the listed performance authorities."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=(
                    "Find performance regressions in this diff. Quantify the "
                    "blast radius in `why` and cite an authoritative reference.\n\n"
                    f"Diff:\n```\n{self.diff_blob(ctx, 5500)}\n```"
                ),
                skill_name=self.name, default_dimension=Dimension.PERFORMANCE,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.perf.fallback", error=str(exc)[:200])
        merged = apply_memory_adjustments(self._dedupe(det + llm), ctx)
        for f in merged:
            f.auto_postable = f.confidence >= 80
        return SkillResult(findings=merged, fallback_used=fallback, **telemetry,
                           payload={"deterministic": len(det), "llm": len(llm)})

    def _deterministic(self, ctx: SkillContext) -> list:
        """Pattern-based catches drawn from Spark + Python perf catalogs."""
        if ctx.pr is None:
            return []
        out = []
        all_specs = [*PERFORMANCE_SPARK, *PERFORMANCE_PY, *SQL_PATTERNS]
        for fc in ctx.pr.files:
            if fc.language not in _PERF_LANGS:
                continue
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                text = "\n".join(hunk.get("lines", []))
                for spec in all_specs:
                    if spec.regex.search(text):
                        loc = start
                        quote = text[:120]
                        for off, ln in enumerate(hunk.get("lines", [])):
                            if spec.regex.search(ln):
                                loc = start + off
                                quote = ln.lstrip("+").strip()
                                break
                        out.append(make_finding(
                            rule_id=spec.rule_id, skill=self.name,
                            dimension=spec.dimension, severity=spec.severity,
                            confidence=82, file=fc.path, line=loc,
                            title=spec.title, why=spec.why, fix=spec.fix,
                            quote=quote[:200],
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
