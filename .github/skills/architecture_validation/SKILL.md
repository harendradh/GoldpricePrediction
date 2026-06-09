# Architecture Validation

> **Auto-generated from `architecture_validation.py` · canonical spec for this skill**

Architecture Validation skill · layer integrity · public API · DI · module cohesion.

Purpose
-------
Catches architectural drift before it ossifies. Operates against a locked
layer order (`ui → api → domain → infra → core`) and flags imports that
violate the dependency direction, public-API changes that break consumers,
and module-cohesion smells (god classes, parameter explosion).

Methodology
-----------
1. **Deterministic import analysis** — parses `from X import Y` / `import X`
   in added diff lines, maps each side to a layer, flags violations
   (lower layer importing from higher layer).
2. **LLM contextual pass** — surfaces issues that need understanding of
   how the classes are wired together: god classes, IoC violations,
   framework leak into domain, missing abstraction boundary.

Authoritative standards consulted
---------------------------------
- Clean Architecture (Uncle Bob)                 https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Domain-Driven Design (Eric Evans)              https://www.domainlanguage.com/ddd/
- SOLID principles                               https://en.wikipedia.org/wiki/SOLID
- Microservices Patterns (Richardson)            https://microservices.io/patterns/
- Refactoring (Fowler) — Code Smells             https://martinfowler.com/refactoring/
- 12-Factor App                                  https://12factor.net/

What this skill catches
-----------------------
- `from infra import …` inside a `core/` or `domain/` module → layer violation
- Public method renamed / removed without `@Deprecated` warm-up window
- Framework imports (`flask`, `django`, `spring`) inside `domain/`
- God classes (>15 public methods or >800-line files)
- Functions with 6+ parameters (constructor / param-object smell)

What this skill explicitly does NOT catch
-----------------------------------------
- Performance of those layers → `performance_analysis`
- Security of public APIs → `security_scan`
- Test coverage of public APIs → `test_coverage_analysis`

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
