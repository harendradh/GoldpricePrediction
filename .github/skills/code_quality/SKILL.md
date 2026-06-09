# Code Quality

> **Auto-generated from `code_quality.py` · canonical spec for this skill**

Code Quality skill · idiom · maintainability · style · simple correctness bugs.

Purpose
-------
Catches the bugs and anti-patterns that a senior reviewer would flag on first read.
Stays in the "is this code well-written" lane and explicitly does NOT cover
security (delegated to `security_scan`), performance (`performance_analysis`),
or architecture (`architecture_validation`).

Methodology
-----------
Two-pass detection:

1. **Deterministic regex pass** — runs first, in-process, no network. Matches
   high-precision patterns drawn from PEP 8, Effective Python, Effective Java,
   and the Python docs' "Common Pitfalls" sections. Findings carry
   confidence ≥ 80 because the patterns are vetted for low false-positive rate.

2. **LLM contextual pass** — runs only if the model is reachable. The model is
   given the diff + the locked standards catalog (PEP-8, PEP-257, Google
   Python Style Guide, Clean Code) and asked to surface issues the regex pass
   can't see (subtle naming problems, complexity that doesn't trip a pattern,
   missing edge-case handling).

Outputs are merged + deduped on (rule_id, file, line). Memory adjustments
(per-repo confidence tuning from past triage decisions) are applied before
returning, then `auto_postable` is flagged if confidence ≥ 80.

Authoritative standards consulted
---------------------------------
- PEP 8 — Style Guide for Python Code        https://peps.python.org/pep-0008/
- PEP 20 — The Zen of Python                 https://peps.python.org/pep-0020/
- PEP 257 — Docstring Conventions            https://peps.python.org/pep-0257/
- PEP 484 — Type Hints                       https://peps.python.org/pep-0484/
- Google Python Style Guide                  https://google.github.io/styleguide/pyguide.html
- Effective Java 3rd Edition (Bloch)         https://www.oreilly.com/library/view/effective-java/9780134686097/
- Clean Code (Robert C. Martin)              https://www.oreilly.com/library/view/clean-code/9780136083238/

What this skill catches
-----------------------
- Bare `except:` clauses → CWE-703, PEP-8
- Mutable default arguments → classic Python footgun (PEP-8, Google Python Style)
- `assert` used as runtime validation → fails under `python -O`
- `print()` instead of structured logging → unobservable in prod
- Silent exception swallowing → CWE-703
- Java `Optional.get()` without check → defeats Optional (Effective Java Item 55)
- Java `String.equals()` with possibly-null lhs → NPE (Effective Java Item 55)
- `new BigDecimal(double)` → IEEE-754 precision loss

What this skill explicitly does NOT catch
-----------------------------------------
- Security holes → `security_scan` owns those
- Performance regressions → `performance_analysis`
- Layer violations → `architecture_validation`
- Missing tests → `test_coverage_analysis`
- Dependency drift → `dependency_audit`

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
