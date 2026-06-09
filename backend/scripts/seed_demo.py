"""Demo seed · populates atlas.db with realistic showcase data.

Creates:
  · 4 repos across 3 teams (ingestion, pre_purposing, data_engineering)
  · 18 pull requests spread across open / merged / closed states
  · ~60 findings across all severity + dimension buckets
  · Triage decisions (accept / dismiss / reply) on most findings
  · Audit log entries matching real reviewer workflow
  · Enough data to showcase Inbox, Triage, Insights, Scorecard, CAB Brief, Settings

Usage:
    cd backend
    ../.venv/Scripts/python.exe scripts/seed_demo.py            # Windows
    ../.venv/bin/python         scripts/seed_demo.py            # Mac / Linux

Idempotent · skips if demo data already present (checks by repo name).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Make project root importable
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.db.models import AuditLog, Finding, PullRequest, Repo, TriageDecision
from app.db.session import SessionLocal, init_db

# ── Deterministic helpers ──────────────────────────────────────
def _ago(days: float = 0, hours: float = 0) -> datetime:
    return datetime.utcnow() - timedelta(days=days, hours=hours)


SEV_ORDER = {"BLOCKER": 1, "MAJOR": 2, "MINOR": 3, "NIT": 4}

# ── Demo data spec ─────────────────────────────────────────────

REPOS = [
    {"full_name": "fiserv-dcs/customer-data-ingestion",  "team": "ingestion",         "default_branch": "main"},
    {"full_name": "fiserv-dcs/payment-event-pipeline",   "team": "ingestion",         "default_branch": "main"},
    {"full_name": "fiserv-dcs/risk-score-service",       "team": "pre_purposing",     "default_branch": "main"},
    {"full_name": "fiserv-dcs/reporting-api",            "team": "data_engineering",  "default_branch": "develop"},
]

# Each PR: (repo_idx, number, title, author, branch, status, verdict, days_ago, files, adds, dels, findings)
# findings: list of (rule_id, pack, severity, dimension, file, line, confidence, title, why, fix)
PRS = [
    # ── customer-data-ingestion ──────────────────────────────
    (0, 101, "feat: add customer PII encryption layer", "alice.chen", "feature/pii-encrypt",
     "open", "improve", 1.2, 8, 312, 45,
     [
        ("security.hardcoded_secret", "security", "BLOCKER", "security",
         "src/ingestion/config.py", 42, 95,
         "Hardcoded AWS secret key",
         "AWS access key `AKIAIOSFODNN7EXAMPLE` committed to source. "
         "Bots scan public repos every 30 min — expect rotation + alert within hours.",
         "Rotate immediately. Load from `aws secretsmanager get-secret-value` or SSM Parameter Store."),
        ("security.pii_in_log", "security", "MAJOR", "security",
         "src/ingestion/processor.py", 118, 88,
         "PII (email + SSN) written to log",
         "Lines 118-119 log `customer.email` and `customer.ssn` at INFO level. "
         "These flow to CloudWatch and Splunk where retention > 7 years.",
         "Log only a masked token: `log.info('processing customer', id=customer.id)`"),
        ("injection.sql_concat", "security", "MAJOR", "security",
         "src/ingestion/db_writer.py", 77, 92,
         "SQL built via string concatenation",
         "Classic injection vector — any unvalidated field in customer payload becomes executable SQL.",
         "Use parameterized queries: `cursor.execute('INSERT INTO ... WHERE id=%s', (cid,))`"),
        ("code.bare_except", "python", "MINOR", "correctness",
         "src/ingestion/processor.py", 203, 85,
         "Bare `except:` clause swallows all exceptions",
         "Catches `SystemExit` and `KeyboardInterrupt`. Silent failures are invisible in prod.",
         "Catch the specific exception: `except (ValueError, KeyError) as exc: logger.error(...)`"),
        ("test.no_sibling_test", "testing", "MINOR", "testing",
         "src/ingestion/processor.py", 0, 72,
         "Net-new code without a sibling test file",
         "303 lines added; no test file in this PR. First feedback comes only when prod breaks.",
         "Add `tests/test_processor.py` covering the happy path + one error path."),
     ]),

    (0, 100, "fix: handle null customer_id in transform step", "bob.patel", "fix/null-cid",
     "merged", "merge", 4.5, 3, 28, 6,
     [
        ("code.none_check_missing", "python", "MINOR", "correctness",
         "src/ingestion/transform.py", 55, 82,
         "Possible NoneType on `customer_id` access",
         "Line 55 accesses `.strip()` on a field that can be None from the upstream source.",
         "Guard: `if customer_id is not None: customer_id = customer_id.strip()`"),
     ]),

    (0, 99, "perf: replace UDF with native Spark functions", "alice.chen", "perf/native-funcs",
     "merged", "merge", 8, 6, 120, 88,
     [
        ("spark.udf_instead_of_native", "pyspark", "MAJOR", "performance",
         "src/ingestion/transforms.py", 34, 90,
         "Python UDF used where `F.regexp_replace` exists",
         "Python UDFs disable Catalyst optimization and serialize every row through the Python process. "
         "On 200M rows this adds ~45 min to the job.",
         "Replace with `F.regexp_replace(col, pattern, replacement)` — same semantics, JVM speed."),
        ("spark.collect_unbounded", "pyspark", "MAJOR", "performance",
         "src/ingestion/transforms.py", 89, 88,
         "`df.collect()` without row limit on 200M-row frame",
         "Pulls entire dataset to driver. Driver OOM at ~50M rows with default 8 GB heap.",
         "Use `.show(20)` for debugging or `df.limit(1000).collect()` for sampling."),
     ]),

    # ── payment-event-pipeline ────────────────────────────────
    (1, 87, "feat: real-time fraud detection integration", "carlos.m", "feature/fraud-rt",
     "open", "block", 0.5, 12, 890, 120,
     [
        ("security.pickle_loads", "security", "BLOCKER", "security",
         "src/fraud/model_loader.py", 22, 97,
         "`pickle.loads` on untrusted model payload",
         "Arbitrary code execution. Any process that can push a model file owns this service. "
         "CWE-502: Deserialization of Untrusted Data.",
         "Use `joblib.load()` with a content-hash check, or switch to ONNX/PMML format."),
        ("security.yaml_load_unsafe", "security", "MAJOR", "security",
         "src/fraud/config_loader.py", 15, 92,
         "`yaml.load()` without SafeLoader",
         "yaml.load() can execute arbitrary Python via `!!python/object` tags in the YAML.",
         "Replace with `yaml.safe_load(stream)` — no behaviour change for config files."),
        ("spark.withcolumn_in_loop", "pyspark", "MAJOR", "performance",
         "src/fraud/feature_eng.py", 67, 90,
         "`withColumn()` called inside Python loop (O(N²) plan)",
         "Each `withColumn()` creates a new logical plan node. "
         "100 iterations → 100-node plan → query planning takes minutes before execution starts.",
         "Collect transforms into a single `select(...)` or use `functools.reduce`."),
        ("arch.layer_violation", "architecture", "MAJOR", "architecture",
         "src/fraud/feature_eng.py", 5, 80,
         "Infrastructure import in domain layer",
         "`from db.postgres import connection_pool` in domain code. "
         "Breaks Clean Architecture: domain must not depend on infra details.",
         "Define a `FeatureStore` interface in domain; inject the Postgres impl at the composition root."),
        ("code.missing_type_hints", "python", "NIT", "correctness",
         "src/fraud/model_loader.py", 1, 70,
         "Public API missing type hints",
         "PEP-484: type hints on public functions aid IDE tooling and catch errors at import time.",
         "Add `-> ModelArtifact` return type and parameter annotations."),
     ]),

    (1, 86, "chore: upgrade kafka-python to 2.0.3", "diana.wu", "chore/kafka-upgrade",
     "merged", "merge", 12, 2, 18, 18,
     [
        ("dep.unpinned_requirement", "dependency", "MINOR", "dependencies",
         "requirements.txt", 14, 82,
         "kafka-python pinned to `>=2.0` (too broad)",
         "Overly loose pin allows future breaking changes to land silently on `pip install`.",
         "Pin to a tested range: `kafka-python>=2.0.3,<3.0`."),
     ]),

    (1, 85, "fix: dead-letter queue retry logic", "carlos.m", "fix/dlq-retry",
     "closed", None, 20, 4, 55, 30,
     [
        ("error.swallowed_exception", "python", "MAJOR", "error_handling",
         "src/pipeline/consumer.py", 88, 85,
         "Exception caught and swallowed in retry loop",
         "Silent failure — message quietly disappears, no alert, dead-letter queue never gets it.",
         "Log at ERROR level and re-raise: `logger.error('consume failed', exc=exc); raise`"),
     ]),

    # ── risk-score-service ────────────────────────────────────
    (2, 54, "feat: credit risk model v3 rollout", "eva.johnson", "feature/risk-v3",
     "open", "improve", 2, 15, 650, 210,
     [
        ("security.hardcoded_secret", "security", "BLOCKER", "security",
         "config/model_config.yaml", 8, 98,
         "Model API key hardcoded in YAML config",
         "Key is readable by anyone with repo access or S3 read. "
         "Rotate + load from Vault/SSM immediately.",
         "Use env var: `api_key: !ENV MODEL_API_KEY`"),
        ("db.add_not_null_no_default", "database", "BLOCKER", "data_model",
         "migrations/0047_add_risk_tier.sql", 12, 95,
         "`ALTER TABLE ADD COLUMN risk_tier NOT NULL` without default",
         "PostgreSQL rewrites the entire table under ACCESS EXCLUSIVE lock. "
         "On a 50M-row table this blocks reads+writes for 8-12 minutes.",
         "Expand/contract: `ADD COLUMN risk_tier TEXT` → backfill → `ALTER SET NOT NULL`."),
        ("spark.shuffle_join", "pyspark", "MAJOR", "performance",
         "src/risk/feature_builder.py", 145, 88,
         "Broadcast hint missing on small-side join",
         "Right-side table is 2 MB (lookups). Without broadcast hint Spark shuffles both sides — "
         "adds 3-4 min on every run.",
         "Wrap: `risk_df.join(broadcast(lookup_df), on='product_code')`."),
        ("test.no_sibling_test", "testing", "MAJOR", "testing",
         "src/risk/scorer.py", 0, 74,
         "600-line scorer rewrite without test update",
         "Model behaviour changed; existing tests were written for v2 logic.",
         "Add regression tests with known score fixtures for v3 thresholds."),
     ]),

    (2, 53, "refactor: extract feature store abstraction", "eva.johnson", "refactor/feat-store",
     "merged", "merge", 18, 10, 340, 290,
     [
        ("arch.god_class", "architecture", "MINOR", "architecture",
         "src/risk/feature_store.py", 1, 75,
         "God class — 22 public methods, 820 lines",
         "Single class owns persistence, transformation, caching, and serving. "
         "Violates SRP; change blast radius is the whole file.",
         "Split into `FeatureWriter`, `FeatureReader`, `FeatureCache` by responsibility."),
     ]),

    (2, 52, "fix: p99 latency spike in score endpoint", "frank.li", "fix/p99-latency",
     "merged", "merge", 25, 5, 90, 45,
     [
        ("resource.open_no_with", "python", "MAJOR", "resource_management",
         "src/risk/model_io.py", 34, 88,
         "`open()` outside `with` statement leaks file descriptor",
         "FD leak accumulates under load until `Too many open files` kills the process.",
         "Replace with `with open(path) as f: data = f.read()`"),
     ]),

    # ── reporting-api ─────────────────────────────────────────
    (3, 31, "feat: add GDPR data-export endpoint", "grace.kim", "feature/gdpr-export",
     "open", "improve", 3, 9, 410, 55,
     [
        ("security.path_traversal", "security", "BLOCKER", "security",
         "src/api/export.py", 67, 96,
         "Path traversal in export filename parameter",
         "User-supplied `filename` param passed to `os.path.join` without sanitisation. "
         "CWE-22: `../../etc/passwd` retrieves arbitrary files.",
         "Validate filename: `if '..' in filename or filename.startswith('/'): raise HTTPException(400)`"),
        ("api.remove_field", "api", "MAJOR", "api_contract",
         "openapi.yaml", 44, 85,
         "Breaking change: `customer_segment` field removed from GET /customers response",
         "Existing consumers deserialise this field. Removal triggers 500s in downstream services.",
         "Deprecate first (add `deprecated: true` + warn header for 1 release), then remove."),
        ("doc.missing_docstring", "documentation", "MINOR", "documentation",
         "src/api/export.py", 12, 72,
         "New public endpoint missing docstring",
         "PEP-257: all public functions need docstrings. Missing args/returns documentation.",
         "Add Google-style docstring with Args, Returns, Raises sections."),
     ]),

    (3, 30, "chore: bump pydantic 1.x → 2.x", "henry.taylor", "chore/pydantic-v2",
     "merged", "merge", 35, 20, 580, 490,
     [
        ("code.mutable_default", "python", "MINOR", "correctness",
         "src/models/response.py", 88, 80,
         "Mutable default argument `fields=[]`",
         "Python creates one list shared across all calls — classic footgun per PEP-8.",
         "Use `fields: list[str] = Field(default_factory=list)` with Pydantic v2."),
     ]),

    (3, 29, "fix: scorecard aggregation incorrect for multi-repo teams", "grace.kim", "fix/scorecard-agg",
     "merged", "merge", 40, 4, 65, 32,
     []),  # clean PR — no findings

    (3, 28, "perf: cache expensive JOIN in reporting queries", "henry.taylor", "perf/report-cache",
     "merged", "merge", 50, 7, 145, 60,
     [
        ("sql.cartesian_join", "sql", "BLOCKER", "performance",
         "src/db/queries.py", 34, 93,
         "Implicit Cartesian join (missing WHERE clause)",
         "Cross-join of `orders × products` at 500k × 200k rows = 100B row intermediate result. "
         "Query will run until timeout or OOM.",
         "Add the join predicate: `WHERE orders.product_id = products.id`"),
     ]),

    # Additional mixed-state PRs across teams for scorecard richness
    (0, 98, "fix: retry logic on Kafka producer timeout", "bob.patel", "fix/kafka-retry",
     "merged", "merge", 60, 3, 40, 15,
     [
        ("error.raise_without_from", "python", "NIT", "error_handling",
         "src/ingestion/kafka_producer.py", 77, 70,
         "`raise X` without `from e` drops exception chain",
         "PEP-3134: exception context is lost, making post-incident debugging harder.",
         "Use `raise RetryError('...') from exc` to preserve the chain."),
     ]),

    (1, 84, "feat: add event schema validation", "diana.wu", "feature/schema-validation",
     "merged", "merge", 65, 11, 220, 30,
     [
        ("governance.naming_violation", "governance", "NIT", "governance",
         "src/pipeline/SchemaValidator.py", 1, 75,
         "Python module name uses PascalCase (should be snake_case)",
         "PEP-8: module names should be lowercase. `SchemaValidator.py` → `schema_validator.py`.",
         "Rename file to `schema_validator.py` and update all imports."),
     ]),

    (2, 51, "fix: model warm-up reduces cold-start p99", "frank.li", "fix/warmup",
     "merged", "merge", 70, 5, 88, 20,
     []),  # clean

    (3, 27, "docs: add OpenAPI examples for all endpoints", "grace.kim", "docs/openapi-examples",
     "merged", "merge", 75, 6, 290, 10,
     []),  # clean docs-only PR
]

# Triage decisions for findings (deterministic list — applied after findings are inserted)
# Format: (repo_idx, pr_number, rule_id, decision, user, note)
TRIAGE = [
    # customer-data-ingestion PR 101
    (0, 101, "code.bare_except",      "accept",  "alice.chen",  "Agreed — catch ValueError specifically."),
    (0, 101, "test.no_sibling_test",  "accept",  "bob.patel",   "Adding tests in follow-up PR."),
    # customer-data-ingestion PR 100
    (0, 100, "code.none_check_missing","accept", "alice.chen",  "Fixed in this PR already."),
    # payment-event-pipeline PR 87
    (1, 87, "code.missing_type_hints", "dismiss", "carlos.m",  "Type hints added in separate typing PR."),
    # payment-event-pipeline PR 86
    (1, 86, "dep.unpinned_requirement","accept",  "diana.wu",  "Will pin in next dependency audit sprint."),
    # payment-event-pipeline PR 85
    (1, 85, "error.swallowed_exception","accept", "carlos.m",  "Good catch — adding to error handling guide."),
    # risk-score-service PR 53
    (2, 53, "arch.god_class",          "accept", "eva.johnson", "Tracked in JIRA RISK-234."),
    # risk-score-service PR 52
    (2, 52, "resource.open_no_with",   "accept", "frank.li",   "Root cause of the FD leak. Fixed."),
    # reporting-api PR 30
    (3, 30, "code.mutable_default",    "accept", "henry.taylor","Classic — added to onboarding checklist."),
    # reporting-api PR 28
    (3, 28, "sql.cartesian_join",      "accept", "grace.kim",  "Critical — caused the incident last month."),
    # ingestion PR 98
    (0, 98,  "error.raise_without_from","accept","bob.patel",  "Good to know about PEP-3134."),
    # event pipeline PR 84
    (1, 84, "governance.naming_violation","dismiss","diana.wu", "Renaming would break 12 import paths."),
]


def _seed(db) -> int:
    """Insert all demo data. Returns count of rows inserted."""
    inserted = 0

    # ── Guard: skip if already seeded ──────────────────────────
    existing = db.execute(
        __import__("sqlalchemy").select(Repo).where(
            Repo.full_name == REPOS[0]["full_name"]
        )
    ).scalar_one_or_none()
    if existing:
        print("  Demo data already present — skipping (delete atlas.db to reseed).")
        return 0

    # ── Repos ──────────────────────────────────────────────────
    repo_objs: dict[int, Repo] = {}
    for i, r in enumerate(REPOS):
        obj = Repo(**r, enabled=True, review_count=0, auto_registered=False)
        db.add(obj)
        db.flush()
        repo_objs[i] = obj
        inserted += 1
        print(f"  repo  {r['full_name']} ({r['team']})")

    # ── PRs + Findings ─────────────────────────────────────────
    pr_map: dict[tuple[int, int], PullRequest] = {}
    finding_map: dict[tuple[int, int, str], Finding] = {}

    for (ri, pr_num, title, author, branch, status, verdict,
         days_ago, files, adds, dels, findings_spec) in PRS:

        pr = PullRequest(
            repo=REPOS[ri]["full_name"],
            number=pr_num,
            sha=f"demo{ri:02d}{pr_num:04d}abc",
            title=title,
            author=author,
            branch=branch,
            status=status,
            verdict=verdict,
            review_state="done" if status in ("merged", "closed") else "done",
            files_changed=files,
            additions=adds,
            deletions=dels,
            diff_text=f"# Demo diff for {title}\n# +{adds}/-{dels} lines across {files} files",
            created_at=_ago(days=days_ago + 0.5),
            updated_at=_ago(days=days_ago * 0.2),
            reviewed_at=_ago(days=days_ago * 0.3) if status in ("merged", "closed", "open") else None,
        )
        db.add(pr)
        db.flush()
        pr_map[(ri, pr_num)] = pr
        inserted += 1

        for (rule_id, pack, severity, dimension, file, line, confidence,
             ftitle, why, fix) in findings_spec:
            f = Finding(
                pull_request_id=pr.id,
                rule_id=rule_id,
                pack=pack,
                severity=severity,
                severity_order=SEV_ORDER.get(severity, 99),
                dimension=dimension,
                file=file,
                line=line,
                confidence=confidence,
                title=ftitle,
                quote=f"# line {line} in {file}",
                why=why,
                fix=fix,
                auto_posted=confidence >= 80,
            )
            db.add(f)
            db.flush()
            finding_map[(ri, pr_num, rule_id)] = f
            inserted += 1

    # ── Triage decisions ───────────────────────────────────────
    for (ri, pr_num, rule_id, decision, user, note) in TRIAGE:
        key = (ri, pr_num, rule_id)
        f = finding_map.get(key)
        if not f:
            continue
        td = TriageDecision(
            finding_id=f.id,
            decision=decision,
            note=note,
            user=user,
            decided_at=_ago(days=0.5, hours=float(abs(hash(rule_id)) % 48)),
        )
        db.add(td)
        inserted += 1

    # ── Audit log entries ──────────────────────────────────────
    audit_entries = []
    for (ri, pr_num, *_) in PRS:
        repo_name = REPOS[ri]["full_name"]
        pr = pr_map[(ri, pr_num)]
        audit_entries.append(AuditLog(
            timestamp=pr.created_at,
            actor="changepilot[bot]",
            action="review.start",
            target=f"{repo_name}#{pr_num}",
            detail={"files": pr.files_changed, "sha": pr.sha},
        ))
        if pr.reviewed_at:
            audit_entries.append(AuditLog(
                timestamp=pr.reviewed_at,
                actor="changepilot[bot]",
                action="review.complete",
                target=f"{repo_name}#{pr_num}",
                detail={"verdict": pr.verdict, "findings": len(pr.findings)},
            ))

    for (ri, pr_num, rule_id, decision, user, note) in TRIAGE:
        key = (ri, pr_num, rule_id)
        f = finding_map.get(key)
        if not f:
            continue
        audit_entries.append(AuditLog(
            timestamp=_ago(days=0.3),
            actor=user,
            action=f"triage.{decision}",
            target=f"finding:{f.id}",
            detail={"rule": rule_id, "note": note[:80] if note else ""},
        ))

    for entry in audit_entries:
        db.add(entry)
        inserted += len(audit_entries)

    # Deduplicate inserted count for logs
    db.commit()
    return inserted


if __name__ == "__main__":
    print("ChangePilot Studio · demo seed")
    print("=" * 50)
    init_db()
    with SessionLocal() as db:
        n = _seed(db)
    if n:
        print(f"\nSeeded {n} rows.")
        print("\nTeams available in the Team Filter:")
        for r in REPOS:
            label = r["team"].replace("_", " ").title()
            print(f"  · {label}  ({r['full_name']})")
        print("\nOpen PRs to explore in Inbox + Triage:")
        for pr in PRS:
            if pr[5] == "open":
                print(f"  · {REPOS[pr[0]]['full_name']} PR #{pr[1]} — {pr[2]}")
    print("\nDone. Start the backend: cd backend && uvicorn app.main:app --reload")
