"""Central catalog of authoritative engineering standards referenced by skills.

Every Finding emitted by the platform carries a `references` list that points
into this catalog. Reviewers (human or AI) can cite the exact standard a
violation breaches, which makes the review comment educational instead of
just prescriptive.

Categories
----------
1. Security frameworks (OWASP, CWE, NIST, SANS, ASVS, PCI-DSS)
2. Language standards (PEP series · Effective Java · Google Style Guides)
3. Architecture (Clean Architecture · DDD · Microservices Patterns)
4. Performance (Spark Tuning Guide · JVM Performance · pyperformance)
5. Operations (12-Factor App · DORA · Site Reliability Engineering)
6. Documentation (PEP-257 · Javadoc · Google Doc Style)
7. Testing (Test Pyramid · F.I.R.S.T · AAA pattern · Test Smells)
8. Database migrations (PostgreSQL · MySQL · Sqitch · Liquibase)
9. Dependencies / Supply chain (OWASP Dep-Check · SLSA · NIST 800-218)
10. Change management (ITIL · ServiceNow · Google SRE Workbook)

Reference convention
--------------------
Each constant is a tuple `(id, label, url)`:
- `id`    : short identifier suitable for inclusion in Finding.references
- `label` : human-readable name shown in review comments
- `url`   : authoritative URL (specification, RFC, or canonical doc)

Use helpers `ref(...)` and `refs(...)` at the bottom to compose lists.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Standard:
    id: str
    label: str
    url: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "url": self.url}


# ─── Security · OWASP ─────────────────────────────────────────────
OWASP_TOP_10_2021               = Standard("OWASP-TOP-10-2021", "OWASP Top 10 2021", "https://owasp.org/Top10/")
OWASP_A01_BROKEN_ACCESS         = Standard("OWASP-A01-2021", "A01:2021 — Broken Access Control", "https://owasp.org/Top10/A01_2021-Broken_Access_Control/")
OWASP_A02_CRYPTO_FAILURES       = Standard("OWASP-A02-2021", "A02:2021 — Cryptographic Failures", "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/")
OWASP_A03_INJECTION             = Standard("OWASP-A03-2021", "A03:2021 — Injection", "https://owasp.org/Top10/A03_2021-Injection/")
OWASP_A04_INSECURE_DESIGN       = Standard("OWASP-A04-2021", "A04:2021 — Insecure Design", "https://owasp.org/Top10/A04_2021-Insecure_Design/")
OWASP_A05_SECURITY_MISCONFIG    = Standard("OWASP-A05-2021", "A05:2021 — Security Misconfiguration", "https://owasp.org/Top10/A05_2021-Security_Misconfiguration/")
OWASP_A06_VULN_COMPONENTS       = Standard("OWASP-A06-2021", "A06:2021 — Vulnerable Components", "https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/")
OWASP_A07_AUTH_FAILURES         = Standard("OWASP-A07-2021", "A07:2021 — Identification and Authentication Failures", "https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/")
OWASP_A08_DATA_INTEGRITY        = Standard("OWASP-A08-2021", "A08:2021 — Software and Data Integrity Failures", "https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/")
OWASP_A09_LOGGING_FAILURES      = Standard("OWASP-A09-2021", "A09:2021 — Security Logging and Monitoring Failures", "https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/")
OWASP_A10_SSRF                  = Standard("OWASP-A10-2021", "A10:2021 — Server-Side Request Forgery", "https://owasp.org/Top10/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/")

OWASP_ASVS_4                    = Standard("OWASP-ASVS-4", "OWASP ASVS 4.0", "https://owasp.org/www-project-application-security-verification-standard/")
OWASP_CHEAT_SQLI                = Standard("OWASP-CHEAT-SQLI", "OWASP SQL Injection Prevention Cheat Sheet", "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html")
OWASP_CHEAT_CRYPTO              = Standard("OWASP-CHEAT-CRYPTO", "OWASP Cryptographic Storage Cheat Sheet", "https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html")
OWASP_CHEAT_LOGGING             = Standard("OWASP-CHEAT-LOGGING", "OWASP Logging Cheat Sheet", "https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html")
OWASP_CHEAT_DESERIALIZATION     = Standard("OWASP-CHEAT-DESERIAL", "OWASP Deserialization Cheat Sheet", "https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html")
OWASP_CHEAT_SECRETS             = Standard("OWASP-CHEAT-SECRETS", "OWASP Secrets Management Cheat Sheet", "https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html")
OWASP_CHEAT_DEPENDENCY          = Standard("OWASP-CHEAT-DEPS", "OWASP Vulnerable Dependency Management Cheat Sheet", "https://cheatsheetseries.owasp.org/cheatsheets/Vulnerable_Dependency_Management_Cheat_Sheet.html")

# ─── Security · CWE ───────────────────────────────────────────────
CWE_22_PATH_TRAVERSAL   = Standard("CWE-22", "CWE-22: Path Traversal", "https://cwe.mitre.org/data/definitions/22.html")
CWE_78_OS_INJECTION     = Standard("CWE-78", "CWE-78: OS Command Injection", "https://cwe.mitre.org/data/definitions/78.html")
CWE_79_XSS              = Standard("CWE-79", "CWE-79: Cross-site Scripting", "https://cwe.mitre.org/data/definitions/79.html")
CWE_89_SQL_INJECTION    = Standard("CWE-89", "CWE-89: SQL Injection", "https://cwe.mitre.org/data/definitions/89.html")
CWE_94_CODE_INJECTION   = Standard("CWE-94", "CWE-94: Code Injection", "https://cwe.mitre.org/data/definitions/94.html")
CWE_200_INFO_EXPOSURE   = Standard("CWE-200", "CWE-200: Exposure of Sensitive Information", "https://cwe.mitre.org/data/definitions/200.html")
CWE_209_ERROR_EXPOSURE  = Standard("CWE-209", "CWE-209: Information Exposure Through Error Message", "https://cwe.mitre.org/data/definitions/209.html")
CWE_259_HARDCODED_PWD   = Standard("CWE-259", "CWE-259: Use of Hard-coded Password", "https://cwe.mitre.org/data/definitions/259.html")
CWE_295_CERT_VALIDATION = Standard("CWE-295", "CWE-295: Improper Certificate Validation", "https://cwe.mitre.org/data/definitions/295.html")
CWE_327_BROKEN_CRYPTO   = Standard("CWE-327", "CWE-327: Use of Broken/Risky Crypto Algorithm", "https://cwe.mitre.org/data/definitions/327.html")
CWE_330_INSUFFICIENT_RND= Standard("CWE-330", "CWE-330: Use of Insufficiently Random Values", "https://cwe.mitre.org/data/definitions/330.html")
CWE_352_CSRF            = Standard("CWE-352", "CWE-352: Cross-Site Request Forgery", "https://cwe.mitre.org/data/definitions/352.html")
CWE_400_RESOURCE_EXHAUST= Standard("CWE-400", "CWE-400: Uncontrolled Resource Consumption", "https://cwe.mitre.org/data/definitions/400.html")
CWE_434_FILE_UPLOAD     = Standard("CWE-434", "CWE-434: Unrestricted File Upload", "https://cwe.mitre.org/data/definitions/434.html")
CWE_476_NPE             = Standard("CWE-476", "CWE-476: NULL Pointer Dereference", "https://cwe.mitre.org/data/definitions/476.html")
CWE_489_DEBUG_FEATURES  = Standard("CWE-489", "CWE-489: Leftover Debug Code", "https://cwe.mitre.org/data/definitions/489.html")
CWE_502_DESERIALIZATION = Standard("CWE-502", "CWE-502: Deserialization of Untrusted Data", "https://cwe.mitre.org/data/definitions/502.html")
CWE_532_LOG_SENSITIVE   = Standard("CWE-532", "CWE-532: Insertion of Sensitive Information into Log File", "https://cwe.mitre.org/data/definitions/532.html")
CWE_546_SUSPICIOUS_CMT  = Standard("CWE-546", "CWE-546: Suspicious Comment", "https://cwe.mitre.org/data/definitions/546.html")
CWE_676_DANGEROUS_FN    = Standard("CWE-676", "CWE-676: Use of Potentially Dangerous Function", "https://cwe.mitre.org/data/definitions/676.html")
CWE_703_EXCEPTION_CHECK = Standard("CWE-703", "CWE-703: Improper Check or Handling of Exceptional Conditions", "https://cwe.mitre.org/data/definitions/703.html")
CWE_730_DOS_REGEX       = Standard("CWE-730", "CWE-730: DoS via Excessive Regex (ReDoS)", "https://cwe.mitre.org/data/definitions/730.html")
CWE_798_HARDCODED_CREDS = Standard("CWE-798", "CWE-798: Use of Hard-coded Credentials", "https://cwe.mitre.org/data/definitions/798.html")
CWE_807_TRUST_BOUNDARY  = Standard("CWE-807", "CWE-807: Reliance on Untrusted Inputs in Security Decision", "https://cwe.mitre.org/data/definitions/807.html")
CWE_829_UNTRUSTED_INC   = Standard("CWE-829", "CWE-829: Inclusion of Functionality from Untrusted Sphere", "https://cwe.mitre.org/data/definitions/829.html")
CWE_915_DYNAMIC_TYPE    = Standard("CWE-915", "CWE-915: Improperly Controlled Modification of Dynamically-Determined Attributes", "https://cwe.mitre.org/data/definitions/915.html")

# ─── Security · NIST ──────────────────────────────────────────────
NIST_SP_800_53          = Standard("NIST-SP-800-53", "NIST SP 800-53 (Security and Privacy Controls)", "https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final")
NIST_SP_800_131A        = Standard("NIST-SP-800-131A", "NIST SP 800-131A (Transitioning Cryptographic Algorithms)", "https://csrc.nist.gov/publications/detail/sp/800-131a/rev-2/final")
NIST_SP_800_218_SSDF    = Standard("NIST-SP-800-218", "NIST SP 800-218 (Secure Software Development Framework)", "https://csrc.nist.gov/publications/detail/sp/800-218/final")
NIST_SP_800_63B_AUTH    = Standard("NIST-SP-800-63B", "NIST SP 800-63B (Digital Identity Guidelines)", "https://pages.nist.gov/800-63-3/sp800-63b.html")

# ─── Security · SANS / PCI ────────────────────────────────────────
SANS_TOP_25             = Standard("SANS-TOP-25", "SANS Top 25 Most Dangerous Software Errors", "https://www.sans.org/top25-software-errors/")
PCI_DSS_4               = Standard("PCI-DSS-4", "PCI DSS 4.0", "https://www.pcisecuritystandards.org/document_library/")

# ─── Python · PEP ─────────────────────────────────────────────────
PEP_8_STYLE             = Standard("PEP-8", "PEP 8 — Style Guide for Python Code", "https://peps.python.org/pep-0008/")
PEP_20_ZEN              = Standard("PEP-20", "PEP 20 — The Zen of Python", "https://peps.python.org/pep-0020/")
PEP_257_DOCSTRINGS      = Standard("PEP-257", "PEP 257 — Docstring Conventions", "https://peps.python.org/pep-0257/")
PEP_343_WITH            = Standard("PEP-343", "PEP 343 — The `with` Statement", "https://peps.python.org/pep-0343/")
PEP_484_TYPE_HINTS      = Standard("PEP-484", "PEP 484 — Type Hints", "https://peps.python.org/pep-0484/")
PEP_492_ASYNCIO         = Standard("PEP-492", "PEP 492 — Coroutines with async/await", "https://peps.python.org/pep-0492/")
PEP_3134_EXCEPTION      = Standard("PEP-3134", "PEP 3134 — Exception Chaining and Embedded Tracebacks", "https://peps.python.org/pep-3134/")
PYTHON_LOGGING_BEST     = Standard("PYTHON-LOG-BEST", "Python Logging HOWTO", "https://docs.python.org/3/howto/logging.html")
PYTHON_ASYNCIO_BEST     = Standard("PYTHON-ASYNCIO-BEST", "asyncio — Concurrency Best Practices", "https://docs.python.org/3/library/asyncio-task.html")
PYTHON_SECRETS_MODULE   = Standard("PYTHON-SECRETS", "Python `secrets` module (cryptographic randomness)", "https://docs.python.org/3/library/secrets.html")

# ─── Java · Effective Java + Oracle ───────────────────────────────
EFFECTIVE_JAVA_3        = Standard("EFFECTIVE-JAVA-3", "Effective Java 3rd Edition (Joshua Bloch)", "https://www.oreilly.com/library/view/effective-java/9780134686097/")
EFFECTIVE_JAVA_55       = Standard("EFFECTIVE-JAVA-ITEM-55", "Effective Java Item 55 — Return Optionals Judiciously", "https://www.oreilly.com/library/view/effective-java/9780134686097/")
EFFECTIVE_JAVA_69       = Standard("EFFECTIVE-JAVA-ITEM-69", "Effective Java Item 69 — Use exceptions only for exceptional conditions", "https://www.oreilly.com/library/view/effective-java/9780134686097/")
EFFECTIVE_JAVA_73       = Standard("EFFECTIVE-JAVA-ITEM-73", "Effective Java Item 73 — Throw appropriate exceptions", "https://www.oreilly.com/library/view/effective-java/9780134686097/")
EFFECTIVE_JAVA_77       = Standard("EFFECTIVE-JAVA-ITEM-77", "Effective Java Item 77 — Don't ignore exceptions", "https://www.oreilly.com/library/view/effective-java/9780134686097/")
ORACLE_JAVA_NAMING      = Standard("ORACLE-JAVA-NAMING", "Java Naming Conventions", "https://www.oracle.com/java/technologies/javase/codeconventions-namingconventions.html")
JAVA_CONCURRENCY_BOOK   = Standard("JCIP", "Java Concurrency in Practice (Goetz et al)", "https://jcip.net/")

# ─── Style guides ─────────────────────────────────────────────────
GOOGLE_PYTHON_STYLE     = Standard("GOOGLE-PY-STYLE", "Google Python Style Guide", "https://google.github.io/styleguide/pyguide.html")
GOOGLE_JAVA_STYLE       = Standard("GOOGLE-JAVA-STYLE", "Google Java Style Guide", "https://google.github.io/styleguide/javaguide.html")
GOOGLE_DOC_STYLE        = Standard("GOOGLE-DOC-STYLE", "Google Developer Documentation Style Guide", "https://developers.google.com/style")
CLEAN_CODE              = Standard("CLEAN-CODE", "Clean Code (Robert C. Martin)", "https://www.oreilly.com/library/view/clean-code/9780136083238/")

# ─── Architecture ─────────────────────────────────────────────────
CLEAN_ARCHITECTURE      = Standard("CLEAN-ARCH", "Clean Architecture (Robert C. Martin)", "https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html")
DDD_EVANS               = Standard("DDD-EVANS", "Domain-Driven Design (Eric Evans)", "https://www.domainlanguage.com/ddd/")
MICROSERVICE_PATTERNS   = Standard("MS-PATTERNS", "Microservices Patterns (Chris Richardson)", "https://microservices.io/patterns/")
TWELVE_FACTOR_APP       = Standard("12-FACTOR", "The Twelve-Factor App", "https://12factor.net/")
FOWLER_REFACTORING      = Standard("FOWLER-REFACTOR", "Refactoring (Martin Fowler) — Code smells", "https://martinfowler.com/refactoring/")
SOLID_PRINCIPLES        = Standard("SOLID", "SOLID Principles", "https://en.wikipedia.org/wiki/SOLID")

# ─── Performance ──────────────────────────────────────────────────
SPARK_TUNING_GUIDE      = Standard("SPARK-TUNING", "Spark Performance Tuning Guide", "https://spark.apache.org/docs/latest/tuning.html")
SPARK_SQL_PERF_GUIDE    = Standard("SPARK-SQL-PERF", "Spark SQL Performance Tuning Guide", "https://spark.apache.org/docs/latest/sql-performance-tuning.html")
DATABRICKS_BEST         = Standard("DBX-BEST", "Databricks Best Practices", "https://docs.databricks.com/en/best-practices.html")
JVM_PERF_BOOK           = Standard("JVM-PERF", "Java Performance: The Definitive Guide", "https://www.oreilly.com/library/view/java-performance-the/9781449363512/")
PYTHON_PERF_TIPS        = Standard("PYTHON-PERF", "Python Performance Tips (official wiki)", "https://wiki.python.org/moin/PythonSpeed/PerformanceTips")
HIGH_PERF_PYTHON        = Standard("HIGH-PERF-PY", "High Performance Python (Gorelick & Ozsvald)", "https://www.oreilly.com/library/view/high-performance-python/9781449361747/")

# ─── Database migrations ──────────────────────────────────────────
PG_DOC_DDL              = Standard("PG-DDL", "PostgreSQL DDL Reference (ALTER TABLE)", "https://www.postgresql.org/docs/current/ddl-alter.html")
PG_LOCKING_BEST         = Standard("PG-LOCK", "PostgreSQL Locking Best Practices", "https://www.postgresql.org/docs/current/explicit-locking.html")
ZERO_DOWNTIME_MIGRATION = Standard("ZERO-DT-MIGRATION", "Strong Migrations Guide (zero-downtime DDL)", "https://github.com/ankane/strong_migrations")
LIQUIBASE_BEST          = Standard("LIQUIBASE-BEST", "Liquibase Best Practices", "https://docs.liquibase.com/concepts/bestpractices.html")
ALEMBIC_GUIDE           = Standard("ALEMBIC", "Alembic Tutorial (Auto-generating Migrations)", "https://alembic.sqlalchemy.org/en/latest/autogenerate.html")
EXPAND_CONTRACT         = Standard("EXPAND-CONTRACT", "Expand-Contract Pattern for Zero-Downtime Schema Change", "https://martinfowler.com/bliki/ParallelChange.html")

# ─── API contract ─────────────────────────────────────────────────
OPENAPI_3_1             = Standard("OPENAPI-3.1", "OpenAPI Specification 3.1", "https://spec.openapis.org/oas/v3.1.0")
GRAPHQL_VERSIONING      = Standard("GRAPHQL-VERSIONING", "GraphQL Versioning Best Practices", "https://graphql.org/learn/best-practices/")
STRIPE_API_VERSIONING   = Standard("STRIPE-API-VER", "Stripe API Versioning Pattern", "https://stripe.com/blog/api-versioning")
SEMANTIC_VERSIONING     = Standard("SEMVER-2", "Semantic Versioning 2.0.0", "https://semver.org/")
RFC_7807_PROBLEM        = Standard("RFC-7807", "RFC 7807 — Problem Details for HTTP APIs", "https://datatracker.ietf.org/doc/html/rfc7807")

# ─── Operations / DORA / SRE ──────────────────────────────────────
DORA_METRICS            = Standard("DORA", "DORA 4 Key Metrics", "https://dora.dev/")
SPACE_FRAMEWORK         = Standard("SPACE", "SPACE Framework for Developer Productivity", "https://queue.acm.org/detail.cfm?id=3454124")
GOOGLE_SRE_BOOK         = Standard("SRE-BOOK", "Google Site Reliability Engineering", "https://sre.google/sre-book/")
ITIL_4_CHANGE_MGMT      = Standard("ITIL-4-CHANGE", "ITIL 4 Change Enablement", "https://www.axelos.com/certifications/propath/itil-4-foundation")
SLSA_FRAMEWORK          = Standard("SLSA", "Supply-chain Levels for Software Artifacts (SLSA)", "https://slsa.dev/")
NIST_CSF_2              = Standard("NIST-CSF-2", "NIST Cybersecurity Framework 2.0", "https://www.nist.gov/cyberframework")

# ─── Testing ──────────────────────────────────────────────────────
TEST_PYRAMID            = Standard("TEST-PYRAMID", "Test Pyramid (Mike Cohn)", "https://martinfowler.com/bliki/TestPyramid.html")
FIRST_TEST_PRINCIPLES   = Standard("FIRST-TESTS", "F.I.R.S.T Test Principles (Robert Martin)", "https://github.com/ghsukumar/SFDC_Best_Practices/wiki/F.I.R.S.T-Principles-of-Unit-Testing")
AAA_PATTERN             = Standard("AAA-PATTERN", "Arrange-Act-Assert Pattern", "http://wiki.c2.com/?ArrangeActAssert")
TEST_SMELLS             = Standard("TEST-SMELLS", "Test Smells Catalog", "https://testsmells.org/")
PYTEST_GOOD_PRACTICES   = Standard("PYTEST-GOOD", "pytest Good Practices", "https://docs.pytest.org/en/stable/explanation/goodpractices.html")

# ─── Documentation / Naming ───────────────────────────────────────
CONVENTIONAL_COMMITS    = Standard("CONVENTIONAL-COMMITS", "Conventional Commits 1.0.0", "https://www.conventionalcommits.org/")
KEEPACHANGELOG          = Standard("KEEPACHANGELOG", "Keep a Changelog", "https://keepachangelog.com/")
CODEOWNERS_DOC          = Standard("CODEOWNERS", "GitHub CODEOWNERS Documentation", "https://docs.github.com/en/repositories/managing-your-repositories-settings-and-features/customizing-your-repository/about-code-owners")
GOOGLE_README_TEMPLATE  = Standard("GOOGLE-README", "Google README Best Practices", "https://github.com/jehna/readme-best-practices")


# ─────────────────────────────────────────────────────────────────
# Convenience: bundle several standards into a list for a finding
# ─────────────────────────────────────────────────────────────────
def refs(*standards: Standard) -> list[str]:
    """Turn a list of Standard refs into the string list Finding.references expects."""
    return [f"{s.label} ({s.url})" for s in standards]


def ref_ids(*standards: Standard) -> list[str]:
    """Compact form · just the short IDs · for cases where URLs would be too noisy."""
    return [s.id for s in standards]


# Catalog accessor — handy for skill-level STANDARDS attributes
ALL_STANDARDS_BY_ID = {
    name: value for name, value in dict(globals()).items()
    if isinstance(value, Standard)
}


def get_standard(standard_id: str) -> Standard | None:
    """Look up a Standard by its short ID."""
    for s in ALL_STANDARDS_BY_ID.values():
        if s.id == standard_id:
            return s
    return None
