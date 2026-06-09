"""Smoke tests · no LLM calls · runnable offline.

Covers the deterministic parts that we can keep CI-stable:
  - Confidence scoring monotonicity + bounds
  - Auto-post routing rules
  - Webhook signature validation (HMAC happy path + rejection)
  - YAML rule loader (uses the actual rules/ fixtures shipped in the repo)
  - JSON extraction from a fuzzy LLM response
  - Spec.md generation from QuickReview payload
"""
from __future__ import annotations

import hashlib
import hmac
import os

# Set env vars BEFORE importing the app · pydantic-settings reads on import.
os.environ.setdefault("DATABRICKS_HOST", "https://example-databricks.test")
os.environ.setdefault("DATABRICKS_TOKEN", "dapi-test")
os.environ.setdefault("GITHUB_TOKEN", "ghp-test")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("ATLAS_RULES_DIR", str(__import__("pathlib").Path(__file__).parent.parent / "rules"))
os.environ.setdefault("ATLAS_PROMPTS_DIR", str(__import__("pathlib").Path(__file__).parent.parent / "prompts"))


def test_confidence_score_bounds() -> None:
    from app.core.confidence import score_finding

    s_low = score_finding(
        rule_id="pyspark.collect_unbounded",
        severity="BLOCKER",
        priority="NORMAL",
        surrounding_context_corroborates=False,
        repo_dismissal_rate=0.9,
        is_heuristic_only=True,
    )
    s_high = score_finding(
        rule_id="sec.sql_string_concat",
        severity="BLOCKER",
        priority="CRITICAL",
        surrounding_context_corroborates=True,
        repo_dismissal_rate=0.0,
        is_heuristic_only=False,
    )
    assert 0 <= s_low <= 100
    assert 0 <= s_high <= 100
    assert s_high > s_low


def test_should_auto_post_blocker_always_posts() -> None:
    from app.core.confidence import should_auto_post

    # BLOCKER always posts regardless of confidence
    assert should_auto_post("BLOCKER", 30) is True
    # NIT below threshold does not
    assert should_auto_post("NIT", 60) is False


def test_webhook_signature_roundtrip() -> None:
    from app.github.webhooks import verify_signature

    body = b'{"action":"opened","number":42}'
    secret = "test-secret"  # matches env var above
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig) is True
    assert verify_signature(body, "sha256=deadbeef") is False
    assert verify_signature(body, None) is False
    assert verify_signature(body, "garbage") is False


def test_load_rule_packs() -> None:
    from app.agents.loaders import load_rule_packs

    packs = load_rule_packs()
    assert "pyspark" in packs
    assert "python" in packs
    assert "security" in packs
    assert "general" in packs
    py = packs["python"]
    assert any(r.id == "python.bare_except" for r in py.rules)


def test_rules_for_languages_always_applies_security() -> None:
    from app.agents.loaders import rules_for_languages

    # Even with only `pyspark` declared, security + general always apply.
    rules = rules_for_languages(["pyspark"])
    rule_ids = {r.id for r in rules}
    assert any(rid.startswith("sec.") for rid in rule_ids)
    assert any(rid.startswith("gen.") for rid in rule_ids)
    assert any(rid.startswith("pyspark.") for rid in rule_ids)
    # `java` rules should NOT be there
    assert not any(rid.startswith("java.") for rid in rule_ids)


def test_language_detection_from_pyspark_content() -> None:
    from app.agents.loaders import detect_languages

    files = [
        ("apps/etl/job.py", "from pyspark.sql import SparkSession\n"),
        ("apps/util/helper.py", "import os\n"),
    ]
    langs = detect_languages(files)
    assert "python" in langs
    assert "pyspark" in langs


def test_dimension_json_extraction_handles_fences() -> None:
    from app.agents.orchestrator import _parse_dimension_report

    fuzzy = (
        "Sure, here's my analysis:\n\n"
        "```json\n"
        '{"dimension":"audit","findings":[{"rule_id":"python.bare_except",'
        '"severity":"MAJOR","dimension":"audit","file":"x.py","line":12,'
        '"title":"bare except","quote":"except:","why":"swallows","fix":"except Exception:"}],'
        '"note":""}'
        "\n```"
    )
    rep = _parse_dimension_report("audit", fuzzy)
    assert rep.dimension == "audit"
    assert len(rep.findings) == 1
    assert rep.findings[0].rule_id == "python.bare_except"


def test_render_spec_md_includes_all_sections() -> None:
    from app.api.v1 import QuickReviewIn, _render_spec_md

    body = QuickReviewIn(
        review_id="PR-4521",
        title="Customer enrichment",
        files=["apps/etl/jobs/customer.py"],
        languages=["pyspark", "python"],
        context="Hot path · 240M rows",
        priorities={"perf": "CRITICAL"},
    )
    md = _render_spec_md(body)
    assert "# Review: Customer enrichment" in md
    assert "## Diff scope" in md
    assert "apps/etl/jobs/customer.py" in md
    assert "## Languages" in md
    assert "pyspark" in md
    assert "## Reviewer priorities" in md
    assert "perf: CRITICAL" in md
