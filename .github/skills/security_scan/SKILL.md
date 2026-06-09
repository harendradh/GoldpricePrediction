# Security Scan

> **Auto-generated from `security_scan.py` · canonical spec for this skill**

Security Scan skill · injection · secrets · weak crypto · PII · unsafe deserialization.

Purpose
-------
The platform's highest-stakes lens. Catches issues that could land the
organization in an incident review or a compliance audit. Always runs (the
`should_run` is forced True) because security findings cannot be skipped
based on language detection or PR signals.

Methodology
-----------
Two-pass detection:

1. **Deterministic regex pass** — precision-tuned patterns drawn from the
   OWASP Cheat Sheet Series and CWE Top 25. Coverage:
   - Secrets: AWS keys, private keys, GitHub/Slack/Databricks PATs, generic
     `key=...` literals
   - Weak crypto: MD5/SHA-1 used for security, non-CSPRNG RNG for tokens
   - Injection: SQL concat, subprocess shell=True, pickle.loads,
     yaml.load (unsafe), eval()
   - PII in logs: SSN/DOB/email/phone in `log.*` calls

2. **LLM contextual pass** — surfaces issues the regex can't:
   subtle injection vectors that depend on data flow, weak auth patterns,
   permissive IAM, deserialization variants in less-common libs,
   improper input validation.

Findings carry references from the OWASP/CWE/NIST catalog. Auto-post
threshold is lower than other skills (70 vs 80) because security
false-negatives are more expensive than false-positives.

Authoritative standards consulted
---------------------------------
- OWASP Top 10 2021                       https://owasp.org/Top10/
- OWASP ASVS 4.0                          https://owasp.org/www-project-application-security-verification-standard/
- OWASP Cheat Sheet Series                https://cheatsheetseries.owasp.org/
- CWE Top 25 Most Dangerous Errors        https://cwe.mitre.org/top25/
- NIST SP 800-53 (Security Controls)      https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- NIST SP 800-131A (Crypto Transition)    https://csrc.nist.gov/publications/detail/sp/800-131a/rev-2/final
- SANS Top 25 Software Errors             https://www.sans.org/top25-software-errors/
- PCI DSS 4.0                             https://www.pcisecuritystandards.org/document_library/

What this skill catches
-----------------------
Injection family (OWASP A03:2021):
- SQL injection via string concat (CWE-89)
- OS command injection / shell=True (CWE-78)
- Code injection via eval/exec (CWE-94, CWE-676)
- Path traversal patterns (CWE-22)

Hardcoded credentials (OWASP A07:2021, CWE-798):
- AWS access keys, GitHub PATs, Databricks PATs, Slack tokens
- PEM private keys
- Generic high-entropy `key/secret/token = "..."` literals

Cryptographic failures (OWASP A02:2021):
- MD5/SHA-1 for security (CWE-327)
- Non-cryptographic RNG for tokens (CWE-330)
- DES/3DES/RC4 (CWE-327)

Unsafe deserialization (OWASP A08:2021, CWE-502):
- pickle.loads on untrusted data
- yaml.load without SafeLoader
- Java ObjectInputStream on untrusted streams

Sensitive data exposure (CWE-200, CWE-532):
- PII (SSN/DOB/email/phone/tax_id) in log calls

Security misconfiguration (OWASP A05:2021):
- Wildcard CORS with credentials
- TLS verification disabled
- Debug mode in production

What this skill explicitly does NOT catch
-----------------------------------------
- Authorization flaws (delegated to `architecture_validation`)
- Race conditions (delegated to `concurrency_analysis`)
- Memory safety (use language-specific tooling)

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
