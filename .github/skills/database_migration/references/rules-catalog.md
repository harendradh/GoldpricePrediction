# Rule catalog · Database Migration

Auto-generated from the pattern dataclasses in
[`../../_shared/patterns.py`](../../_shared/patterns.py).

| rule_id | severity | dimension | reference |
|---------|----------|-----------|-----------|
| _populated at skill startup_ | | | |

Run `python -m skills._shared.patterns --catalog=database_migration` to regenerate
this table from live data.

## How rules are tuned

- **Severity** — BLOCKER (must fix) · MAJOR (should fix) · MINOR · NIT
- **Confidence** — deterministic findings carry ≥ 80; LLM findings vary
- **Auto-post threshold** — set per-skill in `scripts/skill.py`; tuned
  by precision (low FP) and consequence (security tolerates lower
  thresholds because misses are expensive)
