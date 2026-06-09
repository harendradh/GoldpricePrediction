# Test Coverage Analysis

> **Auto-generated from `test_coverage_analysis.py` · canonical spec for this skill**

Test Coverage Analysis skill · missing tests · weak assertions · test smells.

Purpose
-------
Identifies the gap between "code shipped" and "code validated." Catches
public functions added without tests, weak assertions that prove nothing,
and brittle test patterns (timing-dependent, order-dependent).

Methodology
-----------
1. **Deterministic structural pass** — scans the diff for:
   - Non-test source files with substantial additions (>30 lines)
   - No sibling test file in the same PR
   - Test-file additions with weak assertions (assertNotNull only)
2. **LLM contextual pass** — surfaces issues that need semantic reading:
   - New public function lacks any assertion covering its core behavior
   - Edge cases (boundary, error path) untested
   - Timing/order-dependent tests
   - Tests asserting implementation details vs observable behavior

Confidence is moderate (70–82) because "missing tests" is context-dependent
— some PRs are pure refactors, some change behavior. The LLM gets the diff
plus an instruction to skip refactor-only changes.

Authoritative standards consulted
---------------------------------
- Test Pyramid (Mike Cohn / Martin Fowler) https://martinfowler.com/bliki/TestPyramid.html
- F.I.R.S.T. principles (Robert Martin)    https://github.com/ghsukumar/SFDC_Best_Practices/wiki/F.I.R.S.T-Principles-of-Unit-Testing
- AAA pattern (Arrange-Act-Assert)         http://wiki.c2.com/?ArrangeActAssert
- Test Smells catalog                      https://testsmells.org/
- pytest Good Practices                    https://docs.pytest.org/en/stable/explanation/goodpractices.html
- Effective Java Item 77 (Don't ignore exceptions)

What this skill catches
-----------------------
- New public function added without any test in the same PR
- Test assertion that only checks non-null / non-empty (no semantic check)
- Tests with sleep() or time.sleep() (flakiness signal)
- Tests asserting on Map/Set iteration order (order-dependent flakiness)

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
