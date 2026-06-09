# Scorecard Narration

> **Auto-generated from `scorecard_narration.py` · canonical spec for this skill**

Scorecard Narration skill · 2-paragraph LLM analysis of team metrics.

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
