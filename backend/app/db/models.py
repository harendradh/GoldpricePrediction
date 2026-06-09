"""ORM models · PullRequest · Finding · TriageDecision · RuleStat · AuditLog."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────
# Pull request · one row per (repo, pr_number, latest sha)
# ─────────────────────────────────────────────────────────────
class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo: Mapped[str] = mapped_column(String(255), index=True)              # owner/name
    number: Mapped[int] = mapped_column(Integer, index=True)
    sha: Mapped[str] = mapped_column(String(80), index=True)               # head SHA
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str] = mapped_column(String(120))
    branch: Mapped[str] = mapped_column(String(255))

    status: Mapped[str] = mapped_column(String(20), default="open")        # open | merged | closed | draft
    verdict: Mapped[str | None] = mapped_column(String(20), default=None)  # merge | improve | block | running
    review_state: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | done | failed

    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    diff_text: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)

    findings: Mapped[list["Finding"]] = relationship(
        back_populates="pull_request", cascade="all, delete-orphan", order_by="Finding.severity_order"
    )

    __table_args__ = (
        UniqueConstraint("repo", "number", "sha", name="uq_repo_pr_sha"),
        Index("ix_pr_status_updated", "status", "updated_at"),
    )


# ─────────────────────────────────────────────────────────────
# Finding · one row per (PR, rule, file, line) after dedup
# ─────────────────────────────────────────────────────────────
class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id"), index=True)

    rule_id: Mapped[str] = mapped_column(String(120), index=True)         # e.g. pyspark.shuffle_join_small_table
    pack: Mapped[str] = mapped_column(String(40), index=True)             # pyspark, python, ...
    severity: Mapped[str] = mapped_column(String(10), index=True)         # BLOCKER | MAJOR | MINOR | NIT
    severity_order: Mapped[int] = mapped_column(Integer, default=99)      # 1=BLOCKER ... 4=NIT (for ORDER BY)
    dimension: Mapped[str] = mapped_column(String(20))                    # audit/perf/secure/style/test

    file: Mapped[str] = mapped_column(String(500))
    line: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[int] = mapped_column(Integer, default=50)

    title: Mapped[str] = mapped_column(String(500))
    quote: Mapped[str | None] = mapped_column(Text)
    why: Mapped[str] = mapped_column(Text)
    fix: Mapped[str | None] = mapped_column(Text)

    auto_posted: Mapped[bool] = mapped_column(default=False)
    github_comment_id: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    pull_request: Mapped[PullRequest] = relationship(back_populates="findings")
    decision: Mapped["TriageDecision | None"] = relationship(
        back_populates="finding", cascade="all, delete-orphan", uselist=False
    )


# ─────────────────────────────────────────────────────────────
# Triage decision · 1:1 with Finding · captured for memory loop
# ─────────────────────────────────────────────────────────────
class TriageDecision(Base):
    __tablename__ = "triage_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id"), unique=True)

    decision: Mapped[str] = mapped_column(String(20))                    # accept | dismiss | reply
    note: Mapped[str | None] = mapped_column(Text)
    user: Mapped[str] = mapped_column(String(120), default="unknown")
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    finding: Mapped[Finding] = relationship(back_populates="decision")


# ─────────────────────────────────────────────────────────────
# Per-repo rule stats · fuel for the continuous-learning loop
# ─────────────────────────────────────────────────────────────
class RuleStat(Base):
    __tablename__ = "rule_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo: Mapped[str] = mapped_column(String(255), index=True)
    rule_id: Mapped[str] = mapped_column(String(120), index=True)

    fired: Mapped[int] = mapped_column(Integer, default=0)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    dismissed: Mapped[int] = mapped_column(Integer, default=0)
    confidence_adj: Mapped[float] = mapped_column(Float, default=0.0)     # added to base confidence

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("repo", "rule_id", name="uq_repo_rule"),
    )

    @property
    def dismissal_rate(self) -> float:
        total = self.accepted + self.dismissed
        return self.dismissed / total if total else 0.0


# ─────────────────────────────────────────────────────────────
# Audit log · immutable record of state-changing actions
# ─────────────────────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(80))                       # review.start | finding.posted | triage.accept | ...
    target: Mapped[str] = mapped_column(String(255))                      # repo#pr or finding_id
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


# ─────────────────────────────────────────────────────────────
# Repos · which repositories Atlas knows about (onboarded)
# ─────────────────────────────────────────────────────────────
class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)   # owner/name
    team: Mapped[str] = mapped_column(String(80), default="unassigned", index=True) # ingestion | fre | pre_purposing | fsbi | pgb | unassigned
    enabled: Mapped[bool] = mapped_column(default=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    threshold_override: Mapped[int | None] = mapped_column(Integer)                # 0-100 · null = use workspace default
    slack_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    auto_registered: Mapped[bool] = mapped_column(default=False)                   # True if onboarded via webhook
