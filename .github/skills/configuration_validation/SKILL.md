# Configuration Validation

> **Auto-generated from `configuration_validation.py` · canonical spec for this skill**

Configuration Validation skill · CORS · SSL · debug flags · env var hygiene.

Purpose
-------
Catches the small configuration mistakes that translate into large security
incidents: wildcard CORS with credentials, disabled TLS verification, debug
mode hardcoded, secrets committed in `application.yml` / `appsettings.json`.

The 12-Factor App methodology and OWASP A05 (Security Misconfiguration) are
the spine of this skill.

Methodology
-----------
1. **Deterministic regex pass** — high-precision matches on CORS / SSL /
   debug-flag patterns, sourced from OWASP Cheat Sheets and 12-Factor.
2. **LLM contextual pass** — catches issues where the misconfiguration is
   only visible when reading multiple config files together (e.g. dev
   config promoted to prod, secret fields not externalized).

Authoritative standards consulted
---------------------------------
- 12-Factor App                              https://12factor.net/
- OWASP A05 — Security Misconfiguration      https://owasp.org/Top10/A05_2021-Security_Misconfiguration/
- OWASP Secure Headers Project               https://owasp.org/www-project-secure-headers/
- CWE-295 (Cert validation)                  https://cwe.mitre.org/data/definitions/295.html
- CWE-489 (Leftover debug code)              https://cwe.mitre.org/data/definitions/489.html

What this skill catches
-----------------------
- CORS `*` origin with `allow_credentials=True` → token leak vector
- `verify=False` in HTTP clients → TLS bypass
- `DEBUG = True` hardcoded → stack trace + env leakage in prod
- Secrets in committed YAML / JSON config files
- Cookie flags missing (HttpOnly / Secure / SameSite)

What this skill explicitly does NOT catch
-----------------------------------------
- Code-level secret literals (delegated to `security_scan`)
- Database / migration config (delegated to `database_migration`)

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
