"""Pattern library · the deterministic catches every skill draws from.

Each `PatternSpec` is a structured rule definition with:
  · `rule_id`     — short namespaced identifier (e.g. `injection.sql_concat`)
  · `severity`    — BLOCKER / MAJOR / MINOR / NIT
  · `dimension`   — which Dimension the finding belongs to
  · `title`       — one-line summary shown in the review comment
  · `why`         — business-terms explanation of the consequence
  · `fix`         — actionable remediation
  · `references`  — list of authoritative `Standard` objects (OWASP, CWE, PEP, etc.)
  · `regex`       — compiled regex to match in diff `+` lines

Patterns are precision-first · we'd rather under-emit than ship false positives.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern

from Agents.Core.schemas import Dimension, Severity
from skills._shared.standards import (
    Standard,
    # Security · OWASP
    OWASP_A02_CRYPTO_FAILURES, OWASP_A03_INJECTION, OWASP_A05_SECURITY_MISCONFIG,
    OWASP_A07_AUTH_FAILURES, OWASP_A08_DATA_INTEGRITY, OWASP_A09_LOGGING_FAILURES,
    OWASP_A10_SSRF,
    OWASP_ASVS_4, OWASP_CHEAT_SQLI, OWASP_CHEAT_CRYPTO, OWASP_CHEAT_LOGGING,
    OWASP_CHEAT_DESERIALIZATION, OWASP_CHEAT_SECRETS, OWASP_CHEAT_DEPENDENCY,
    # Security · CWE
    CWE_22_PATH_TRAVERSAL, CWE_78_OS_INJECTION, CWE_89_SQL_INJECTION,
    CWE_94_CODE_INJECTION, CWE_209_ERROR_EXPOSURE,
    CWE_259_HARDCODED_PWD, CWE_295_CERT_VALIDATION, CWE_327_BROKEN_CRYPTO,
    CWE_330_INSUFFICIENT_RND, CWE_476_NPE,
    CWE_489_DEBUG_FEATURES, CWE_502_DESERIALIZATION,
    CWE_532_LOG_SENSITIVE, CWE_546_SUSPICIOUS_CMT, CWE_676_DANGEROUS_FN,
    CWE_703_EXCEPTION_CHECK, CWE_730_DOS_REGEX,
    CWE_798_HARDCODED_CREDS, CWE_829_UNTRUSTED_INC,
    # NIST
    NIST_SP_800_131A, NIST_SP_800_218_SSDF,
    # Python
    PEP_8_STYLE, PEP_257_DOCSTRINGS, PEP_343_WITH, PEP_492_ASYNCIO,
    PEP_3134_EXCEPTION,
    PYTHON_LOGGING_BEST, PYTHON_ASYNCIO_BEST, PYTHON_SECRETS_MODULE,
    # Java
    EFFECTIVE_JAVA_55, EFFECTIVE_JAVA_69, EFFECTIVE_JAVA_73, EFFECTIVE_JAVA_77,
    ORACLE_JAVA_NAMING, JAVA_CONCURRENCY_BOOK,
    # Style
    GOOGLE_PYTHON_STYLE, GOOGLE_JAVA_STYLE, GOOGLE_DOC_STYLE, CLEAN_CODE,
    # Performance
    SPARK_TUNING_GUIDE, SPARK_SQL_PERF_GUIDE, DATABRICKS_BEST, PYTHON_PERF_TIPS,
    # Operations
    TWELVE_FACTOR_APP,
    # Migrations
    PG_DOC_DDL, PG_LOCKING_BEST, ZERO_DOWNTIME_MIGRATION, EXPAND_CONTRACT,
    # APIs
    OPENAPI_3_1, SEMANTIC_VERSIONING, RFC_7807_PROBLEM,
    # Supply chain
    SLSA_FRAMEWORK,
)


@dataclass(frozen=True)
class PatternSpec:
    """One deterministic pattern · catches a specific bug class with citations."""
    rule_id: str
    severity: Severity
    dimension: Dimension
    title: str
    why: str
    fix: str
    references: list[Standard] = field(default_factory=list)
    regex: Pattern[str] = field(default_factory=lambda: re.compile(r"$^"))

    def reference_strings(self) -> list[str]:
        """Return the human-readable reference list for Finding.references."""
        return [f"{s.label} — {s.url}" for s in self.references]


# ─── Secrets ──────────────────────────────────────────────────
# Hardcoded credentials are CWE-798 (and PCI-DSS req 8). Any secret in
# source equals immediate rotation + audit.
SECRETS: list[PatternSpec] = [
    PatternSpec(
        rule_id="secret.aws_access_key",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="AWS Access Key ID committed to source",
        why=("Hardcoded AWS keys grant programmatic access to the account. "
             "Once leaked publicly, they're typically abused within minutes by "
             "cryptominer bots scraping GitHub."),
        fix="Rotate the key immediately; load from AWS Secrets Manager / SSM Parameter Store; never commit credentials.",
        references=[CWE_798_HARDCODED_CREDS, OWASP_A07_AUTH_FAILURES, OWASP_CHEAT_SECRETS],
        regex=re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    ),
    PatternSpec(
        rule_id="secret.private_key",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="PEM-formatted private key committed",
        why=("Private keys enable impersonation and decryption of historical "
             "traffic. Any private key in source is considered burned the moment "
             "it lands on the remote."),
        fix="Rotate the keypair immediately; use a secret manager or KMS-backed key.",
        references=[CWE_798_HARDCODED_CREDS, OWASP_A02_CRYPTO_FAILURES, OWASP_CHEAT_SECRETS],
        regex=re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    PatternSpec(
        rule_id="secret.github_pat",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="GitHub Personal Access Token in source",
        why="GitHub PATs grant repo read/write per the token's scopes; abuse is automated by credential scanners.",
        fix="Revoke immediately; use GitHub Actions OIDC or GitHub App tokens for CI auth.",
        references=[CWE_798_HARDCODED_CREDS, OWASP_A07_AUTH_FAILURES, OWASP_CHEAT_SECRETS],
        regex=re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
    ),
    PatternSpec(
        rule_id="secret.databricks_pat",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="Databricks Personal Access Token in source",
        why="Databricks PATs grant workspace access · enables data exfiltration + job execution.",
        fix="Rotate the token via the workspace UI; use Databricks Secret Scopes; prefer OAuth M2M for CI.",
        references=[CWE_798_HARDCODED_CREDS, OWASP_A07_AUTH_FAILURES, OWASP_CHEAT_SECRETS],
        regex=re.compile(r"\bdapi[a-f0-9]{32}\b"),
    ),
    PatternSpec(
        rule_id="secret.slack_token",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="Slack token committed",
        why="Slack tokens (`xox*`) allow message read/post · risks impersonation and data exfiltration via Slack channels.",
        fix="Revoke at api.slack.com; rotate the webhook; load from env.",
        references=[CWE_798_HARDCODED_CREDS, OWASP_CHEAT_SECRETS],
        regex=re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ),
    PatternSpec(
        rule_id="secret.generic_token",
        severity=Severity.MAJOR, dimension=Dimension.SECURITY,
        title="Likely hardcoded credential literal",
        why="String literal pattern `key/secret/token/password = '...'` with high-entropy content suggests committed credential.",
        fix="Externalize via env vars (12-Factor App principle III) or a secret manager.",
        references=[CWE_798_HARDCODED_CREDS, OWASP_CHEAT_SECRETS, TWELVE_FACTOR_APP],
        regex=re.compile(r"['\"](?:api_?key|secret|token|password)['\"]\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", re.IGNORECASE),
    ),
]

# ─── Weak crypto ──────────────────────────────────────────────
# CWE-327 (broken cryptographic algorithm) + NIST SP 800-131A transition guidance.
CRYPTO: list[PatternSpec] = [
    PatternSpec(
        rule_id="crypto.md5_used",
        severity=Severity.MAJOR, dimension=Dimension.SECURITY,
        title="MD5 used in a security context",
        why=("MD5 is broken for collision-resistance · practical attacks exist since 2008 "
             "(SHA-1 since 2017). Acceptable only for non-security checksums (e.g. ETag)."),
        fix="Use SHA-256 (or BLAKE2 for performance-critical hashing).",
        references=[CWE_327_BROKEN_CRYPTO, NIST_SP_800_131A, OWASP_A02_CRYPTO_FAILURES, OWASP_CHEAT_CRYPTO],
        regex=re.compile(r"hashlib\.md5\(|MessageDigest\.getInstance\(['\"]MD5"),
    ),
    PatternSpec(
        rule_id="crypto.sha1_used",
        severity=Severity.MAJOR, dimension=Dimension.SECURITY,
        title="SHA-1 used in a security context",
        why="SHA-1 collisions (SHAttered, 2017) make it unsuitable for signing/auth. NIST deprecated it for cryptographic signatures in 2030.",
        fix="Use SHA-256 (or SHA-3-256 / BLAKE2).",
        references=[CWE_327_BROKEN_CRYPTO, NIST_SP_800_131A, OWASP_A02_CRYPTO_FAILURES, OWASP_CHEAT_CRYPTO],
        regex=re.compile(r"hashlib\.sha1\(|MessageDigest\.getInstance\(['\"]SHA-?1"),
    ),
    PatternSpec(
        rule_id="crypto.random_for_token",
        severity=Severity.MAJOR, dimension=Dimension.SECURITY,
        title="Non-cryptographic RNG used for security token",
        why=("`random.random()` / `Math.random()` use Mersenne Twister · output is predictable after "
             "observing ~624 values. Attackers can reverse-engineer the seed."),
        fix="Use `secrets.token_urlsafe()` (Python) or `SecureRandom` (Java) for any token/nonce/salt.",
        references=[CWE_330_INSUFFICIENT_RND, OWASP_A02_CRYPTO_FAILURES, PYTHON_SECRETS_MODULE],
        regex=re.compile(r"token\s*=\s*random\.|password\s*=\s*random\."),
    ),
]

# ─── Injection / unsafe input handling ────────────────────────
# Injection is the #3 OWASP risk (A03:2021) · always BLOCKER when user input touches it.
INJECTION: list[PatternSpec] = [
    PatternSpec(
        rule_id="injection.sql_concat",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="SQL built via string concatenation",
        why="String-concat SQL is the canonical injection vector · attacker controls query structure once their input lands unfiltered.",
        fix="Parameterize: `cursor.execute(\"SELECT ... WHERE id = %s\", (user_id,))`. Never trust client input.",
        references=[CWE_89_SQL_INJECTION, OWASP_A03_INJECTION, OWASP_CHEAT_SQLI, OWASP_ASVS_4],
        regex=re.compile(r"(SELECT|INSERT|UPDATE|DELETE).*[\"']\s*\+\s*\w+|cursor\.execute\([\"'].*['\"]\s*%\s*\w+", re.IGNORECASE),
    ),
    PatternSpec(
        rule_id="injection.shell_true",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="subprocess invoked with shell=True",
        why="`shell=True` interprets metacharacters · injection-equivalent the moment any arg is user-influenced.",
        fix="Pass args as a list and keep `shell=False` (the default).",
        references=[CWE_78_OS_INJECTION, OWASP_A03_INJECTION],
        regex=re.compile(r"subprocess\.(?:Popen|call|run|check_output)\([^)]*shell\s*=\s*True"),
    ),
    PatternSpec(
        rule_id="injection.pickle_loads",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="pickle.loads on untrusted data",
        why="pickle deserialization is RCE-equivalent · the format can construct arbitrary Python objects on load.",
        fix="Use JSON (or a constrained schema parser like `marshmallow` / `pydantic`). Never pickle untrusted data.",
        references=[CWE_502_DESERIALIZATION, OWASP_A08_DATA_INTEGRITY, OWASP_CHEAT_DESERIALIZATION],
        regex=re.compile(r"pickle\.loads?\s*\("),
    ),
    PatternSpec(
        rule_id="injection.yaml_unsafe_load",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="yaml.load without SafeLoader",
        why="Default `yaml.load` instantiates arbitrary Python objects (RCE-equivalent). Documented as `unsafe` since PyYAML 5.1.",
        fix="Use `yaml.safe_load()` (or `yaml.load(..., Loader=yaml.SafeLoader)`).",
        references=[CWE_502_DESERIALIZATION, OWASP_A08_DATA_INTEGRITY, OWASP_CHEAT_DESERIALIZATION],
        regex=re.compile(r"yaml\.load\((?![^)]*Loader=)"),
    ),
    PatternSpec(
        rule_id="injection.eval_used",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="Use of eval()",
        why="`eval` on any caller-influenced string equals RCE. Even for 'sanitized' input · sanitization is wrong-shaped.",
        fix="Use a domain-specific parser (`ast.literal_eval` for literal data; a real interpreter for complex DSL).",
        references=[CWE_94_CODE_INJECTION, CWE_676_DANGEROUS_FN, OWASP_A03_INJECTION],
        regex=re.compile(r"\beval\s*\("),
    ),
]

# ─── PII in logs ──────────────────────────────────────────────
# Logging PII violates data-classification policy at most enterprises and is
# captured by OWASP A09 (logging failures) + CWE-532.
PII_LOGGING: list[PatternSpec] = [
    PatternSpec(
        rule_id="pii.in_log",
        severity=Severity.BLOCKER, dimension=Dimension.SECURITY,
        title="PII written to application log",
        why=("Logging SSN/DOB/email/phone/tax-ID lands customer PII in every "
             "downstream system that ingests logs · data-classification breach."),
        fix="Remove the PII field; log a tokenized identifier only; redact at the log handler if you can't remove at source.",
        references=[CWE_532_LOG_SENSITIVE, OWASP_A09_LOGGING_FAILURES, OWASP_CHEAT_LOGGING],
        regex=re.compile(
            r"log(?:ger)?\.(?:info|warn|error|debug)\([^)]*"
            r"(ssn|dob|date_of_birth|email|phone_number|tax_id|cust_phone)",
            re.IGNORECASE,
        ),
    ),
]

# ─── Correctness · Python ─────────────────────────────────────
# Drawn from PEP 8 (style), Effective Python (Brett Slatkin), and the
# Python docs' "common pitfalls" sections.
CORRECTNESS_PY: list[PatternSpec] = [
    PatternSpec(
        rule_id="py.bare_except",
        severity=Severity.MAJOR, dimension=Dimension.ERROR_HANDLING,
        title="Bare `except:` clause",
        why="Bare except swallows KeyboardInterrupt, SystemExit, MemoryError · masks fatal conditions you never wanted to catch.",
        fix="Use `except Exception:` (or narrower · catch the specific class).",
        references=[CWE_703_EXCEPTION_CHECK, PEP_8_STYLE, PYTHON_LOGGING_BEST],
        regex=re.compile(r"^\+\s*except\s*:\s*$"),
    ),
    PatternSpec(
        rule_id="py.mutable_default_arg",
        severity=Severity.BLOCKER, dimension=Dimension.CORRECTNESS,
        title="Mutable default argument",
        why=("Default `[]` / `{}` is created once at function-definition time and shared across calls · "
             "silent state leakage between calls. Classic Python footgun."),
        fix="Use `None` as default; instantiate inside the function: `if items is None: items = []`.",
        references=[PEP_8_STYLE, GOOGLE_PYTHON_STYLE],
        regex=re.compile(r"^\+\s*def\s+\w+\([^)]*=\s*(\[\]|\{\})"),
    ),
    PatternSpec(
        rule_id="py.assert_in_production",
        severity=Severity.MAJOR, dimension=Dimension.CORRECTNESS,
        title="assert used as a runtime check",
        why="`python -O` strips asserts · so production runs without your check. Asserts are for tests, not validation.",
        fix="Raise an explicit exception (`raise ValueError(\"...\")`).",
        references=[CWE_703_EXCEPTION_CHECK, PEP_8_STYLE],
        regex=re.compile(r"^\+\s*assert\s+"),
    ),
    PatternSpec(
        rule_id="py.print_instead_of_log",
        severity=Severity.MINOR, dimension=Dimension.DOCUMENTATION,
        title="print() instead of structured logger",
        why="`print()` bypasses log levels, structured fields, and routing · unobservable in prod stacks.",
        fix="Use `logger.info(...)` / `logger.debug(...)` with structured fields.",
        references=[PYTHON_LOGGING_BEST, OWASP_CHEAT_LOGGING],
        regex=re.compile(r"^\+\s*print\s*\("),
    ),
    PatternSpec(
        rule_id="py.except_swallow_exception",
        severity=Severity.MAJOR, dimension=Dimension.ERROR_HANDLING,
        title="Exception caught and silently swallowed",
        why="`except: pass` (or `except Exception: pass`) hides the failure mode · debugging becomes archaeology.",
        fix="Log the exception with stack trace, or re-raise after handling.",
        references=[CWE_703_EXCEPTION_CHECK, PEP_3134_EXCEPTION, PYTHON_LOGGING_BEST],
        regex=re.compile(r"^\+\s*except\b.*:\s*$\n^\+\s*pass", re.MULTILINE),
    ),
]

# ─── Correctness · Java ───────────────────────────────────────
# Mostly drawn from Effective Java 3rd Edition.
CORRECTNESS_JAVA: list[PatternSpec] = [
    PatternSpec(
        rule_id="java.optional_get_no_check",
        severity=Severity.MAJOR, dimension=Dimension.CORRECTNESS,
        title="Optional.get() without isPresent() check",
        why="`Optional.get()` throws NoSuchElementException when empty · this defeats the purpose of Optional entirely.",
        fix="Use `.orElseThrow(...)`, `.orElseGet(...)`, or `.ifPresent(...)`.",
        references=[EFFECTIVE_JAVA_55],
        regex=re.compile(r"\.get\(\)\s*[;.)]"),
    ),
    PatternSpec(
        rule_id="java.string_equals_swap",
        severity=Severity.MAJOR, dimension=Dimension.CORRECTNESS,
        title="String.equals with variable on left",
        why="`var.equals(\"literal\")` throws NPE if `var` is null · `\"literal\".equals(var)` is null-safe.",
        fix="Flip the comparison: `\"literal\".equals(var)` (or use `Objects.equals`).",
        references=[EFFECTIVE_JAVA_55, GOOGLE_JAVA_STYLE],
        regex=re.compile(r"\w+\.equals\(['\"]"),
    ),
    PatternSpec(
        rule_id="java.bigdecimal_double_ctor",
        severity=Severity.MAJOR, dimension=Dimension.CORRECTNESS,
        title="BigDecimal constructed from double",
        why="`new BigDecimal(0.1)` carries IEEE-754 representation error (`0.1000000000000000055511151231257827021181583404541015625`).",
        fix="Use `BigDecimal.valueOf(0.1)` (parses through String) or `new BigDecimal(\"0.1\")`.",
        references=[EFFECTIVE_JAVA_55],
        regex=re.compile(r"new\s+BigDecimal\s*\(\s*\d+\.\d+\s*\)"),
    ),
]

# ─── Performance · Spark / PySpark ────────────────────────────
# Drawn from Apache Spark official tuning guide + Databricks best practices.
PERFORMANCE_SPARK: list[PatternSpec] = [
    PatternSpec(
        rule_id="perf.collect_unbounded",
        severity=Severity.BLOCKER, dimension=Dimension.PERFORMANCE,
        title="Unbounded df.collect() / df.toPandas()",
        why=("Materializes the full DataFrame to the driver · OOM the moment the dataset exceeds "
             "driver heap. Common in dev → silently scales catastrophically in prod."),
        fix="Use `.write` to a sink, `.take(N)` for sampling, or `.toLocalIterator()` for streaming reads.",
        references=[SPARK_TUNING_GUIDE, DATABRICKS_BEST],
        regex=re.compile(r"\.(?:collect|toPandas)\s*\(\s*\)"),
    ),
    PatternSpec(
        rule_id="perf.repartition_to_one",
        severity=Severity.MAJOR, dimension=Dimension.PERFORMANCE,
        title="coalesce(1) / repartition(1) in hot path",
        why="Forces all data through a single executor · the entire pipeline runs sequentially on one core.",
        fix="Repartition once at the final sink, not in intermediate steps. Prefer `partitionBy` for partitioned writes.",
        references=[SPARK_TUNING_GUIDE, SPARK_SQL_PERF_GUIDE],
        regex=re.compile(r"\.(?:coalesce|repartition)\s*\(\s*1\s*\)"),
    ),
    PatternSpec(
        rule_id="perf.withcolumn_in_loop",
        severity=Severity.MAJOR, dimension=Dimension.PERFORMANCE,
        title="withColumn() inside a Python loop",
        why=("Each `withColumn` rebuilds the logical plan · N columns → O(N²) plan construction. "
             "Catalyst optimizer can't help past a few dozen iterations."),
        fix="Build a list of `F.col(...)` and use `df.select(*cols)`, or `df.withColumns({...})` in Spark 3.3+.",
        references=[SPARK_SQL_PERF_GUIDE, DATABRICKS_BEST],
        regex=re.compile(r"for\s+\w+\s+in\s+.*:\s*\n.*\.withColumn\(", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="perf.implicit_cross_join",
        severity=Severity.BLOCKER, dimension=Dimension.PERFORMANCE,
        title="join() without on= condition",
        why="Implicit Cartesian product · row count explodes multiplicatively (1M × 1M = 1T rows).",
        fix="Always pass `on=`. If cross-join is intentional, use `.crossJoin(other)` to make it explicit.",
        references=[SPARK_SQL_PERF_GUIDE, SPARK_TUNING_GUIDE],
        regex=re.compile(r"\.join\(\s*\w+\s*\)(?!\s*\.on)"),
    ),
]

# ─── Performance · Python generic ─────────────────────────────
PERFORMANCE_PY: list[PatternSpec] = [
    PatternSpec(
        rule_id="perf.requests_no_timeout",
        severity=Severity.MAJOR, dimension=Dimension.PERFORMANCE,
        title="requests call without timeout",
        why="Default is no timeout · the call can block your process forever on a hung peer. Single such call can stall an entire worker pool.",
        fix="Always specify `timeout=(connect_secs, read_secs)`, e.g. `timeout=(3, 30)`.",
        references=[PYTHON_PERF_TIPS],
        regex=re.compile(r"requests\.(?:get|post|put|delete|patch)\([^)]*\)"),
    ),
    PatternSpec(
        rule_id="perf.string_concat_in_loop",
        severity=Severity.MINOR, dimension=Dimension.PERFORMANCE,
        title="String concatenation in a loop",
        why="Each iteration allocates a new string (Python strings are immutable) · O(N²) total work.",
        fix="Append to a list and `''.join(parts)` at the end. ~10× faster on 10k iterations.",
        references=[PYTHON_PERF_TIPS],
        regex=re.compile(r"for\s+\w+\s+in\s+.*:\s*\n.*\+=\s*['\"]", re.MULTILINE),
    ),
]

# ─── SQL ──────────────────────────────────────────────────────
SQL_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="sql.cartesian_join",
        severity=Severity.BLOCKER, dimension=Dimension.PERFORMANCE,
        title="Implicit cross join in SQL",
        why="`FROM A, B` without WHERE produces a Cartesian product · explodes the result set.",
        fix="Use explicit `INNER JOIN ... ON ...` so the join key is visible to the optimizer.",
        references=[SPARK_SQL_PERF_GUIDE],
        regex=re.compile(r"FROM\s+\w+\s*,\s*\w+\s+(?!WHERE)", re.IGNORECASE),
    ),
    PatternSpec(
        rule_id="sql.no_where_on_destructive",
        severity=Severity.BLOCKER, dimension=Dimension.CORRECTNESS,
        title="DELETE / UPDATE without WHERE",
        why="Destroys the entire table contents · most expensive 60-second mistake in your career.",
        fix="Always include WHERE; if intentional full-table action, use TRUNCATE explicitly (logged differently).",
        references=[OWASP_ASVS_4],
        regex=re.compile(r"^\+\s*(DELETE FROM|UPDATE)\s+\w+\s*;", re.IGNORECASE | re.MULTILINE),
    ),
]

# ─── Configuration ─────────────────────────────────────────────
CONFIG_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="config.cors_wildcard_credentials",
        severity=Severity.MAJOR, dimension=Dimension.SECURITY,
        title="Wildcard CORS combined with credentials",
        why="Allowing `*` origin with `credentials: true` violates the CORS spec · some browsers still allow it → tokens leak to attacker origins.",
        fix="Allowlist exact origins, or set `allow_credentials=False` if you don't need cookie-auth.",
        references=[OWASP_A05_SECURITY_MISCONFIG, CWE_295_CERT_VALIDATION],
        regex=re.compile(r"allow_origins\s*=\s*\[\s*['\"]\*['\"]\s*\].*allow_credentials\s*=\s*True", re.DOTALL),
    ),
    PatternSpec(
        rule_id="config.ssl_disabled",
        severity=Severity.MAJOR, dimension=Dimension.SECURITY,
        title="SSL certificate verification disabled",
        why="`verify=False` accepts any TLS certificate · enables MITM via local CA injection.",
        fix="Trust the system CA bundle (`verify=True` is the default). If your CA is private, point `verify=` at the bundle path.",
        references=[CWE_295_CERT_VALIDATION, OWASP_A02_CRYPTO_FAILURES],
        regex=re.compile(r"verify\s*=\s*False"),
    ),
    PatternSpec(
        rule_id="config.debug_in_prod",
        severity=Severity.MAJOR, dimension=Dimension.SECURITY,
        title="Debug mode hardcoded enabled",
        why="Debug-mode responses leak stack traces, env vars, and secrets to clients. Per OWASP A05 (Security Misconfiguration).",
        fix="Drive from env var: `DEBUG = os.getenv('DEBUG', '0') == '1'`.",
        references=[CWE_489_DEBUG_FEATURES, OWASP_A05_SECURITY_MISCONFIG, TWELVE_FACTOR_APP],
        regex=re.compile(r"^\+\s*(?:DEBUG|debug)\s*=\s*True", re.MULTILINE),
    ),
]

# ─── Test patterns ────────────────────────────────────────────
TEST_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="test.assert_only_not_none",
        severity=Severity.NIT, dimension=Dimension.TESTING,
        title="Test assertion only checks non-null",
        why="`assertNotNull(x)` proves the variable was set · doesn't prove the behavior was correct.",
        fix="Assert on actual values: `assertEquals(expected, x)` or `assertEquals(expected.field, x.field)`.",
        references=[EFFECTIVE_JAVA_77, CLEAN_CODE],
        regex=re.compile(r"(assertNotNull|assertIsNotNone)\s*\(\s*\w+\s*\)\s*[;)]"),
    ),
]


# ─── Error handling ────────────────────────────────────────────
# Catches the error-handling smells from Effective Java Items 69-77 and
# Python's PEP-3134.  Bare except, swallowed exceptions, and printStackTrace
# all defeat the observability contract.
ERROR_HANDLING_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="error.bare_except",
        severity=Severity.MAJOR, dimension=Dimension.ERROR_HANDLING,
        title="Bare `except:` clause",
        why=("Bare except catches `SystemExit`/`KeyboardInterrupt` and masks bugs. "
             "PEP-8 § Programming Recommendations forbids it."),
        fix="Catch the specific exception: `except ValueError:` or `except (KeyError, IndexError):`.",
        references=[CWE_703_EXCEPTION_CHECK, PEP_8_STYLE, PEP_3134_EXCEPTION],
        regex=re.compile(r"^\+\s*except\s*:", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="error.swallowed",
        severity=Severity.MAJOR, dimension=Dimension.ERROR_HANDLING,
        title="Exception swallowed silently (`pass`)",
        why=("Silent `except: pass` (or `except Exception: pass`) erases the "
             "failure signal — Effective Java Item 77 explicitly forbids this."),
        fix="At minimum log via the structured logger; surface or re-raise if the caller needs to know.",
        references=[EFFECTIVE_JAVA_77, CWE_703_EXCEPTION_CHECK],
        regex=re.compile(r"^\+\s*except[^:]*:\s*\n\s*pass\b", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="error.print_stack_trace",
        severity=Severity.MAJOR, dimension=Dimension.ERROR_HANDLING,
        title="`e.printStackTrace()` instead of structured logging",
        why=("Goes to stderr and is invisible to log aggregation; can leak to "
             "users in some servlet containers (CWE-209)."),
        fix="Use `logger.error(\"...\", e)` (SLF4J) or `logger.exception(...)` (Python).",
        references=[CWE_209_ERROR_EXPOSURE, EFFECTIVE_JAVA_77],
        regex=re.compile(r"\.printStackTrace\s*\(\s*\)"),
    ),
    PatternSpec(
        rule_id="error.raise_without_cause",
        severity=Severity.MINOR, dimension=Dimension.ERROR_HANDLING,
        title="`raise X` inside `except` drops the original cause",
        why="Loses the chain that PEP-3134 was designed to preserve · makes debugging harder.",
        fix="Use `raise X from e` (or `raise X(...) from None` to intentionally suppress).",
        references=[PEP_3134_EXCEPTION, CWE_703_EXCEPTION_CHECK],
        regex=re.compile(r"^\+\s*raise\s+\w+\([^)]*\)\s*$", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="error.catch_throwable",
        severity=Severity.MAJOR, dimension=Dimension.ERROR_HANDLING,
        title="Catching `Throwable` / `Error`",
        why="Swallows JVM errors (OOM, StackOverflow) the runtime needs to abort cleanly.",
        fix="Catch `Exception` or a specific subtype; let `Error` propagate.",
        references=[EFFECTIVE_JAVA_77, CWE_703_EXCEPTION_CHECK],
        regex=re.compile(r"catch\s*\(\s*(Throwable|Error)\b"),
    ),
]

# ─── Concurrency ────────────────────────────────────────────────
# Threads, asyncio, double-checked-locking — the classic foot-guns.
CONCURRENCY_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="concurrency.sync_in_async",
        severity=Severity.MAJOR, dimension=Dimension.CONCURRENCY,
        title="Blocking call inside `async def`",
        why=("`time.sleep` / `requests.get` blocks the event loop · per PEP-492 "
             "and the asyncio docs, use `await asyncio.sleep` / `httpx.AsyncClient`."),
        fix="`await asyncio.sleep(n)` · use `httpx.AsyncClient` for HTTP · `aiofiles` for I/O.",
        references=[PEP_492_ASYNCIO, PYTHON_ASYNCIO_BEST],
        regex=re.compile(r"^\+\s*(time\.sleep|requests\.(get|post|put|delete))\s*\(", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="concurrency.thread_no_name",
        severity=Severity.NIT, dimension=Dimension.CONCURRENCY,
        title="`Thread()` without `name=` makes debugging hard",
        why="Anonymous threads show as `Thread-N` in stack traces; per Java Concurrency in Practice §3, always name threads.",
        fix="Pass a descriptive `name=` (Python) or use a named `ThreadFactory` (Java).",
        references=[JAVA_CONCURRENCY_BOOK],
        regex=re.compile(r"^\+\s*(Thread|threading\.Thread)\s*\(\s*target", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="concurrency.double_checked_locking_java",
        severity=Severity.MAJOR, dimension=Dimension.CONCURRENCY,
        title="Double-checked locking without `volatile`",
        why="Classic Java broken-DCL pattern · without `volatile` the JIT can publish a partially-constructed instance.",
        fix="Use a static-holder idiom or mark the singleton field `volatile`.",
        references=[JAVA_CONCURRENCY_BOOK, EFFECTIVE_JAVA_77],
        regex=re.compile(r"if\s*\(\s*instance\s*==\s*null\s*\)\s*\{[^}]*synchronized"),
    ),
    PatternSpec(
        rule_id="concurrency.mutable_default_threadlocal",
        severity=Severity.MAJOR, dimension=Dimension.CONCURRENCY,
        title="Mutable global state without thread-local guard",
        why="Module-level `dict()` / `list()` shared across threads invites data races; cite Java Concurrency Item 1 (mutable shared state is the root of evil).",
        fix="Use `threading.local()`, `contextvars.ContextVar`, or pass state through arguments.",
        references=[JAVA_CONCURRENCY_BOOK],
        regex=re.compile(r"^\+(?!.*threading\.local)(?:[A-Z_][A-Z_0-9]+)\s*=\s*(\{\}|\[\])\s*$", re.MULTILINE),
    ),
]

# ─── Resource management ────────────────────────────────────────
# PEP-343 `with`, try-with-resources in Java, finally close.
RESOURCE_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="resource.open_no_with",
        severity=Severity.MAJOR, dimension=Dimension.RESOURCE_MANAGEMENT,
        title="`open()` without `with` statement",
        why=("Manual `open()` without `with` leaks file descriptors on exception "
             "paths · PEP-343 introduced `with` precisely for this case."),
        fix="`with open(path) as f: ...` · always · everywhere.",
        references=[PEP_343_WITH, CWE_703_EXCEPTION_CHECK],
        regex=re.compile(r"^\+\s*\w+\s*=\s*open\s*\(", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="resource.connection_no_close",
        severity=Severity.MAJOR, dimension=Dimension.RESOURCE_MANAGEMENT,
        title="DB/HTTP connection allocated outside `with`",
        why="Leaked connections exhaust the pool · symptoms appear minutes later as `pool timeout` in unrelated requests.",
        fix="Use the library's context manager (`with conn:` / `with httpx.Client() as c:`).",
        references=[PEP_343_WITH],
        regex=re.compile(r"^\+\s*\w+\s*=\s*(psycopg2|sqlite3|httpx|requests)\.(connect|Session|Client)\s*\(", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="resource.threadpool_no_shutdown",
        severity=Severity.MAJOR, dimension=Dimension.RESOURCE_MANAGEMENT,
        title="`ExecutorService` / `ThreadPoolExecutor` without explicit shutdown",
        why="Non-daemon threadpools block JVM/process exit · also leak threads across hot reloads.",
        fix="Wrap in try-with-resources (Java 19+) or `with ThreadPoolExecutor() as ex:` (Python).",
        references=[JAVA_CONCURRENCY_BOOK, PEP_343_WITH],
        regex=re.compile(r"Executors\.(newFixedThreadPool|newCachedThreadPool|newSingleThreadExecutor)"),
    ),
]

# ─── Dependency / supply chain ──────────────────────────────────
DEPENDENCY_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="dep.unpinned_requirement",
        severity=Severity.MAJOR, dimension=Dimension.DEPENDENCIES,
        title="Unpinned requirement (no version constraint)",
        why=("Floating versions break reproducible builds and let upstream "
             "breaking changes land silently. NIST SP 800-218 SSDF PW.4.1 "
             "requires pinned dependencies."),
        fix="Pin to a known-good version range (e.g. `requests>=2.31,<3`).",
        references=[NIST_SP_800_218_SSDF, OWASP_CHEAT_DEPENDENCY, SLSA_FRAMEWORK],
        regex=re.compile(r"^\+(?!\s*#)[a-zA-Z_][\w\-]+\s*$", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="dep.git_url_in_requirements",
        severity=Severity.MAJOR, dimension=Dimension.DEPENDENCIES,
        title="Git URL pinned to a branch (mutable)",
        why="`git+https://…@main` resolves to a moving target · same install, different code tomorrow.",
        fix="Pin to a commit SHA or a tagged release.",
        references=[NIST_SP_800_218_SSDF, SLSA_FRAMEWORK],
        regex=re.compile(r"git\+https?://[^#@\s]+@(main|master|develop|dev)\b"),
    ),
    PatternSpec(
        rule_id="dep.wildcard_version",
        severity=Severity.MAJOR, dimension=Dimension.DEPENDENCIES,
        title="Wildcard / `latest` version specifier",
        why="`*` or `latest` defeats the lockfile and reproducibility.",
        fix="Use semver caret/tilde constraints; commit the lockfile.",
        references=[SEMANTIC_VERSIONING, NIST_SP_800_218_SSDF],
        regex=re.compile(r":\s*[\"\']?(?:\*|latest)[\"\']?\s*[,}]"),
    ),
]

# ─── Database migrations ────────────────────────────────────────
DB_MIGRATION_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="db.add_not_null_no_default",
        severity=Severity.BLOCKER, dimension=Dimension.DATA_MODEL,
        title="`ALTER TABLE … ADD COLUMN … NOT NULL` without default",
        why=("On Postgres this rewrites the whole table while holding an "
             "ACCESS EXCLUSIVE lock — outage-class downtime."),
        fix="Use expand/contract: add nullable → backfill → set NOT NULL with `SET DEFAULT` separately.",
        references=[PG_DOC_DDL, PG_LOCKING_BEST, ZERO_DOWNTIME_MIGRATION, EXPAND_CONTRACT],
        regex=re.compile(r"ADD\s+COLUMN\s+\w+[^,;]*\s+NOT\s+NULL(?!\s+DEFAULT)", re.IGNORECASE),
    ),
    PatternSpec(
        rule_id="db.drop_column",
        severity=Severity.BLOCKER, dimension=Dimension.DATA_MODEL,
        title="`DROP COLUMN` without expand/contract dance",
        why="Old replicas / app instances still reference the column · drop hits them as a SELECT failure.",
        fix="Stop reading first (deploy code) → wait one release → then DROP.",
        references=[EXPAND_CONTRACT, ZERO_DOWNTIME_MIGRATION],
        regex=re.compile(r"DROP\s+COLUMN\s+\w+", re.IGNORECASE),
    ),
    PatternSpec(
        rule_id="db.rename_column",
        severity=Severity.BLOCKER, dimension=Dimension.DATA_MODEL,
        title="`RENAME COLUMN` is not zero-downtime",
        why="A rename atomically breaks every reader that hasn't deployed the new name.",
        fix="Add new column → dual-write → backfill → switch reads → drop old (4-step expand/contract).",
        references=[EXPAND_CONTRACT, ZERO_DOWNTIME_MIGRATION],
        regex=re.compile(r"RENAME\s+COLUMN\s+\w+\s+TO\s+\w+", re.IGNORECASE),
    ),
    PatternSpec(
        rule_id="db.create_index_no_concurrently",
        severity=Severity.MAJOR, dimension=Dimension.DATA_MODEL,
        title="Postgres `CREATE INDEX` without `CONCURRENTLY`",
        why="Plain CREATE INDEX takes ACCESS EXCLUSIVE for the duration · writes block.",
        fix="`CREATE INDEX CONCURRENTLY` and split into its own migration (cannot run in a transaction).",
        references=[PG_DOC_DDL, PG_LOCKING_BEST],
        regex=re.compile(r"^\s*CREATE\s+(UNIQUE\s+)?INDEX\s+(?!CONCURRENTLY)\w+", re.IGNORECASE | re.MULTILINE),
    ),
]

# ─── API contracts ──────────────────────────────────────────────
API_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="api.remove_field",
        severity=Severity.BLOCKER, dimension=Dimension.API_CONTRACT,
        title="Breaking change · field removed from response",
        why="Existing consumers will fail to deserialize. Semantic Versioning § 8 requires a major bump.",
        fix="Deprecate first (one release), then remove. Or version the endpoint (v1 → v2).",
        references=[OPENAPI_3_1, SEMANTIC_VERSIONING],
        regex=re.compile(r"^-\s*[\"\']?\w+[\"\']?\s*:", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="api.type_change",
        severity=Severity.BLOCKER, dimension=Dimension.API_CONTRACT,
        title="Breaking change · field type narrowed",
        why="Tightening a type (`integer`→`string`, `nullable: true`→`false`) rejects previously-valid payloads.",
        fix="Add a new field with the new type and deprecate the old; never narrow in place.",
        references=[OPENAPI_3_1, SEMANTIC_VERSIONING],
        regex=re.compile(r"^-\s*(type|nullable)\s*:", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="api.error_not_rfc7807",
        severity=Severity.MINOR, dimension=Dimension.API_CONTRACT,
        title="Error response missing RFC 7807 envelope",
        why="Ad-hoc error shapes force every client to write a custom parser. RFC 7807 (problem+json) is the universal contract.",
        fix="Wrap errors in `{type, title, status, detail, instance}` per RFC 7807.",
        references=[RFC_7807_PROBLEM],
        regex=re.compile(r"^\+\s*[\"\']error[\"\']\s*:\s*[\"\']\w+[\"\']", re.MULTILINE),
    ),
]

# ─── Documentation ──────────────────────────────────────────────
DOC_PATTERNS: list[PatternSpec] = [
    PatternSpec(
        rule_id="doc.missing_docstring_public",
        severity=Severity.MINOR, dimension=Dimension.DOCUMENTATION,
        title="Public function added without docstring",
        why="PEP-257 requires docstrings on public functions; Google Doc Style requires Args/Returns/Raises.",
        fix="Add a one-line summary + Args/Returns/Raises sections.",
        references=[PEP_257_DOCSTRINGS, GOOGLE_DOC_STYLE],
        regex=re.compile(r"^\+def\s+[a-z_][\w]*\s*\([^)]*\)\s*(?:->\s*[^:]+)?:\s*$", re.MULTILINE),
    ),
    PatternSpec(
        rule_id="doc.todo_without_owner",
        severity=Severity.NIT, dimension=Dimension.DOCUMENTATION,
        title="TODO/FIXME without owner or ticket reference",
        why="Ownerless TODOs become permanent · CWE-546 calls these out as a maintenance smell.",
        fix="Reference an issue (`# TODO(#123): …`) or a person (`# TODO(@alice): …`).",
        references=[CWE_546_SUSPICIOUS_CMT, CLEAN_CODE],
        regex=re.compile(r"^\+.*\b(TODO|FIXME|XXX|HACK)\b(?!\s*[\(\[])", re.MULTILINE),
    ),
]


def all_pattern_groups() -> dict[str, list[PatternSpec]]:
    return {
        "secrets": SECRETS,
        "crypto": CRYPTO,
        "injection": INJECTION,
        "pii_logging": PII_LOGGING,
        "correctness_python": CORRECTNESS_PY,
        "correctness_java": CORRECTNESS_JAVA,
        "performance_spark": PERFORMANCE_SPARK,
        "performance_python": PERFORMANCE_PY,
        "sql": SQL_PATTERNS,
        "config": CONFIG_PATTERNS,
        "test": TEST_PATTERNS,
        "error_handling": ERROR_HANDLING_PATTERNS,
        "concurrency": CONCURRENCY_PATTERNS,
        "resource": RESOURCE_PATTERNS,
        "dependency": DEPENDENCY_PATTERNS,
        "db_migration": DB_MIGRATION_PATTERNS,
        "api": API_PATTERNS,
        "doc": DOC_PATTERNS,
    }
