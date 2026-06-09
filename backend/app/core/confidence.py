"""Confidence scoring · deterministic · drives Tier 3 routing.

A finding's confidence (0-100) decides whether it auto-posts to the PR or
goes into the human triage queue. See § "Confidence scoring" in the v2 SRS.
"""
from __future__ import annotations

from app.config import settings

# Rule-pattern types that are very reliable (deterministic AST/text match).
HIGH_TRUST_PACKS = {"security", "general"}


def score_finding(
    *,
    rule_id: str,
    severity: str,
    priority: str = "NORMAL",
    surrounding_context_corroborates: bool = True,
    repo_dismissal_rate: float = 0.0,
    is_heuristic_only: bool = False,
) -> int:
    """Compute a 0-100 confidence score.

    Signals (positive):
      + 40  base for a pattern-based rule match
      + 20  pattern is unambiguous in the diff text
      + 15  surrounding code corroborates the smell
      + 10  no prior dismissals on this rule for this repo
      + 10  spec/PR description corroborates the priority for this dimension
      + 5   security rule with BLOCKER severity (extra trust)

    Signals (negative):
      - 30  rule has been dismissed >50% of the time on this repo
      - 15  rule is heuristic-only (not a deterministic pattern)
      - 10  source context insufficient

    Clamped to [0, 100].
    """
    score = 40                                    # base · all findings come from rule match

    score += 20                                   # we cite the rule_id explicitly, assume pattern is exact
    if surrounding_context_corroborates:
        score += 15
    if repo_dismissal_rate < 0.3:
        score += 10
    if priority in {"HIGH", "CRITICAL"}:
        score += 10
    if severity == "BLOCKER" and rule_id.startswith("sec."):
        score += 5

    if repo_dismissal_rate > 0.5:
        score -= 30
    if is_heuristic_only:
        score -= 15
    if not surrounding_context_corroborates:
        score -= 10

    return max(0, min(100, score))


def should_auto_post(severity: str, confidence: int) -> bool:
    """Whether a finding posts directly to the PR or goes to triage.

    Tier 3 policy: only auto-post when confidence ≥ workspace threshold.
    BLOCKER findings still post regardless of confidence (they're rare and
    critical), unless settings.atlas_block_on_blocker is off.
    """
    if severity == "BLOCKER":
        return True
    return confidence >= settings.atlas_auto_post_threshold
