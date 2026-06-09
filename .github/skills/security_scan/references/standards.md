# Authoritative standards — Security Scan

The references this skill cites in its findings.

Every standard in this list has a stable canonical URL · these aren't
opinions, they're external authorities a reviewer can verify.

- `OWASP_TOP_10_2021`
- `OWASP_ASVS_4`
- `OWASP_A02_CRYPTO_FAILURES`
- `OWASP_A03_INJECTION`
- `OWASP_A05_SECURITY_MISCONFIG`
- `OWASP_A07_AUTH_FAILURES`
- `OWASP_A08_DATA_INTEGRITY`
- `OWASP_A09_LOGGING_FAILURES`
- `OWASP_CHEAT_SQLI`
- `OWASP_CHEAT_CRYPTO`
- `OWASP_CHEAT_LOGGING`
- `OWASP_CHEAT_DESERIALIZATION`
- `OWASP_CHEAT_SECRETS`
- `CWE_78_OS_INJECTION if False else CWE_89_SQL_INJECTION`
- `CWE_295_CERT_VALIDATION`
- `CWE_327_BROKEN_CRYPTO`
- `CWE_330_INSUFFICIENT_RND`
- `CWE_502_DESERIALIZATION`
- `CWE_532_LOG_SENSITIVE`
- `CWE_798_HARDCODED_CREDS`
- `NIST_SP_800_53`
- `NIST_SP_800_131A`
- `SANS_TOP_25`

## Why we cite externally

Engineers shouldn't have to trust an AI's word. By grounding every
finding in a published standard (OWASP A03, CWE-89, PEP-8 §E501, etc.),
the review comment becomes verifiable in seconds — open the URL, confirm,
move on. False positives get caught faster, true positives carry weight.
