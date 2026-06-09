# Performance Analysis

> **Auto-generated from `performance_analysis.py` · canonical spec for this skill**

Performance Analysis skill · Spark · O(n²) · I/O · UDF cost · memory.

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

---

## How this skill runs

The skill is a deterministic-first reviewer. Two passes:

1. **Deterministic pass** — regex + structural checks drawn from the pattern
   catalog in [`../_shared/patterns.py`](../_shared/patterns.py). Findings
   carry confidence ≥ 80 because patterns are precision-tuned. No network
   required.

2. **LLM contextual pass** — only runs if a model is reachable. The model
   gets the diff + the authoritative-standards catalog inlined into its
   system prompt and is required to cite a reference in every finding.

If the model is unreachable, the deterministic pass still runs and the
skill returns whatever it caught with `fallback_used=True`.

## Implementation

The runnable code lives in [`scripts/skill.py`](scripts/skill.py). It
self-registers on import via `@register_skill`.

## References

- [`references/standards.md`](references/standards.md) — full list of authoritative refs with URLs
- [`references/examples.md`](references/examples.md) — good-vs-bad code snippets the skill flags
- [`references/rules-catalog.md`](references/rules-catalog.md) — enumerated rules + severity

## Output contract

Returns a `SkillResult` with:

- `findings: list[Finding]` — each carries `rule_id`, severity, dimension,
  file/line, why/fix, and a `references` array of `"Label — URL"` strings
- `model_calls`, `input_tokens`, `output_tokens`, `estimated_cost_usd`
- `fallback_used: bool` — true if LLM pass failed
- `payload: dict` — typically `{"deterministic": N, "llm": M}`

Findings with `confidence ≥ threshold` are flagged `auto_postable=True`
and can be posted to the PR by the host agent without manual review.
