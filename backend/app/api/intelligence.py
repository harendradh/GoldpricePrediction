"""Engineering Intelligence + Governance endpoints.

Three capabilities, all riding on data Atlas already collects:

1. **Scorecard** · per-team aggregate metrics (blocker-leakage, dismissal rate,
   cycle time, dimension mix, queue depth, top reviewers, 7-day trend).
   Pure SQL aggregations over PullRequest / Finding / TriageDecision / Repo.

2. **CAB Brief** · auto-generated change-management memo per PR, assembled
   from the diff + findings + triage decisions + audit log via Databricks
   Claude. Output is markdown ready to paste into ServiceNow / JIRA.

3. **AI Decision Ledger** · unified timeline view that joins audit_log +
   findings + triage_decisions so any reviewer can answer "what did Atlas
   say about this, and why did we ship anyway?" without digging through Slack.

These three give Atlas a defensible position: nobody else has the AI-decision
trail data, so nobody else can build these reports.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.db.models import AuditLog, Finding, PullRequest, Repo, TriageDecision
from app.db.session import get_session

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1")


# ═════════════════════════════════════════════════════════════════
# 1 · Engineering Health Scorecard
# ═════════════════════════════════════════════════════════════════
class ScorecardMetrics(BaseModel):
    team: str
    team_label: str
    window_days: int
    total_prs: int
    open_prs: int
    findings_total: int
    findings_per_pr: float
    blockers_caught: int
    blocker_leakage_rate: float           # blockers dismissed and merged anyway / total blockers
    dismissal_rate: float                  # dismissed / (accepted + dismissed)
    auto_post_rate: float                  # auto_posted / total findings
    median_cycle_time_hours: float | None  # PR created → reviewed
    queue_depth: int                       # findings awaiting triage
    dimension_mix: dict[str, int]          # audit/perf/secure/style/test counts
    top_reviewers: list[dict[str, Any]]    # [{user, decisions}]
    daily_findings: list[dict[str, Any]]   # last N days · [{date, count}]


_TEAM_LABELS = {
    "all":           "All teams",
    "ingestion":     "Ingestion Team",
    "fre":           "FRE Team",
    "pre_purposing": "Pre-Purposing Team",
    "fsbi":          "FSBI Team",
    "pgb":           "Peer Group Bench Marking Team",
    "unassigned":    "Unassigned",
}


def _repos_for_team(db: Session, team: str) -> list[str] | None:
    """Returns the list of repo full_names that belong to the given team.
    Returns None for `team == "all"` (= no scoping)."""
    if team == "all":
        return None
    return list(db.execute(select(Repo.full_name).where(Repo.team == team)).scalars().all())


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    n = len(xs)
    if n % 2 == 1:
        return float(xs[n // 2])
    return (xs[n // 2 - 1] + xs[n // 2]) / 2.0


@router.get("/scorecard", response_model=ScorecardMetrics)
def scorecard(
    db: Annotated[Session, Depends(get_session)],
    team: str = Query("all", description="all | ingestion | fre | pre_purposing | fsbi | pgb | unassigned"),
    days: int = Query(30, ge=1, le=365),
) -> ScorecardMetrics:
    since = datetime.utcnow() - timedelta(days=days)
    repo_names = _repos_for_team(db, team)

    # Base PR filter
    pr_stmt = select(PullRequest).where(PullRequest.created_at >= since)
    if repo_names is not None:
        pr_stmt = pr_stmt.where(PullRequest.repo.in_(repo_names) if repo_names else PullRequest.repo == "__none__")
    prs = db.execute(pr_stmt).scalars().all()

    pr_ids = [p.id for p in prs]
    total_prs = len(prs)
    open_prs = sum(1 for p in prs if p.status == "open")

    # Cycle time · created → reviewed (only completed reviews)
    cycle_hours = [
        (p.reviewed_at - p.created_at).total_seconds() / 3600.0
        for p in prs
        if p.reviewed_at and p.created_at
    ]
    median_cycle = _median(cycle_hours)

    # Findings scoped to those PRs
    if pr_ids:
        findings = db.execute(
            select(Finding).where(Finding.pull_request_id.in_(pr_ids))
        ).scalars().all()
    else:
        findings = []

    findings_total = len(findings)
    blockers_total = sum(1 for f in findings if f.severity == "BLOCKER")
    auto_posted = sum(1 for f in findings if f.auto_posted)

    # Triage decisions on those findings
    finding_ids = [f.id for f in findings]
    if finding_ids:
        decisions = db.execute(
            select(TriageDecision).where(TriageDecision.finding_id.in_(finding_ids))
        ).scalars().all()
    else:
        decisions = []
    decision_by_finding = {d.finding_id: d for d in decisions}

    accepted = sum(1 for d in decisions if d.decision == "accept")
    dismissed = sum(1 for d in decisions if d.decision == "dismiss")
    blocker_dismissed_and_merged = sum(
        1 for f in findings
        if f.severity == "BLOCKER"
        and decision_by_finding.get(f.id)
        and decision_by_finding[f.id].decision == "dismiss"
        and any(p.id == f.pull_request_id and p.status == "merged" for p in prs)
    )

    # Awaiting triage = no decision yet
    queue_depth = sum(1 for f in findings if f.id not in decision_by_finding)

    # Dimension distribution
    dimension_mix: dict[str, int] = {}
    for f in findings:
        dimension_mix[f.dimension] = dimension_mix.get(f.dimension, 0) + 1

    # Top reviewers · who is triaging the most
    reviewer_counts: dict[str, int] = {}
    for d in decisions:
        reviewer_counts[d.user] = reviewer_counts.get(d.user, 0) + 1
    top_reviewers = [
        {"user": u, "decisions": c}
        for u, c in sorted(reviewer_counts.items(), key=lambda x: -x[1])[:5]
    ]

    # Daily-findings sparkline · last min(days, 14) buckets
    bucket_days = min(days, 14)
    bucket_start = datetime.utcnow() - timedelta(days=bucket_days)
    daily: dict[str, int] = {}
    for f in findings:
        if f.created_at >= bucket_start:
            key = f.created_at.strftime("%Y-%m-%d")
            daily[key] = daily.get(key, 0) + 1
    daily_findings = [
        {"date": (bucket_start + timedelta(days=i)).strftime("%Y-%m-%d"),
         "count": daily.get((bucket_start + timedelta(days=i)).strftime("%Y-%m-%d"), 0)}
        for i in range(bucket_days)
    ]

    return ScorecardMetrics(
        team=team,
        team_label=_TEAM_LABELS.get(team, team),
        window_days=days,
        total_prs=total_prs,
        open_prs=open_prs,
        findings_total=findings_total,
        findings_per_pr=round(findings_total / total_prs, 2) if total_prs else 0.0,
        blockers_caught=blockers_total,
        blocker_leakage_rate=round(blocker_dismissed_and_merged / blockers_total, 3) if blockers_total else 0.0,
        dismissal_rate=round(dismissed / (accepted + dismissed), 3) if (accepted + dismissed) else 0.0,
        auto_post_rate=round(auto_posted / findings_total, 3) if findings_total else 0.0,
        median_cycle_time_hours=round(median_cycle, 1) if median_cycle is not None else None,
        queue_depth=queue_depth,
        dimension_mix=dimension_mix,
        top_reviewers=top_reviewers,
        daily_findings=daily_findings,
    )


# ═════════════════════════════════════════════════════════════════
# 2 · CAB Brief · Change-Request Auto-Generator
# ═════════════════════════════════════════════════════════════════
class CABBriefOut(BaseModel):
    pr_id: int
    repo: str
    number: int
    title: str
    generated_at: datetime
    markdown: str
    risk_level: str  # low | medium | high


@router.post("/cab-brief/{pr_id}", response_model=CABBriefOut)
async def generate_cab_brief(
    pr_id: int,
    db: Annotated[Session, Depends(get_session)],
) -> CABBriefOut:
    """Generate a change-management brief (ServiceNow / JIRA ready) from a PR.

    The brief assembles deterministic facts (files touched, findings, decisions,
    approvers) and asks Databricks Claude to write the narrative sections
    (summary · blast radius · rollback). Falls back to a fully-deterministic
    template if the LLM is unreachable so the endpoint never 500s during a demo.
    """
    pr = db.get(PullRequest, pr_id)
    if not pr:
        raise HTTPException(404, "PR not found")

    findings = list(pr.findings)
    blockers = [f for f in findings if f.severity == "BLOCKER"]
    majors = [f for f in findings if f.severity == "MAJOR"]
    accepted = [f for f in findings if f.decision and f.decision.decision == "accept"]
    dismissed = [f for f in findings if f.decision and f.decision.decision == "dismiss"]

    # Risk score = highest-severity un-dismissed finding + diff size
    if blockers and any(f.decision is None or f.decision.decision != "dismiss" for f in blockers):
        risk = "high"
    elif majors and pr.files_changed and pr.files_changed > 10:
        risk = "high"
    elif majors:
        risk = "medium"
    elif pr.files_changed and pr.files_changed > 20:
        risk = "medium"
    else:
        risk = "low"

    # Repo + team
    repo_row = db.execute(select(Repo).where(Repo.full_name == pr.repo)).scalar_one_or_none()
    team_label = _TEAM_LABELS.get(repo_row.team if repo_row else "unassigned", "Unassigned")

    # Approvers · users who triaged
    approvers = sorted({f.decision.user for f in findings if f.decision and f.decision.user})

    # Audit chronology for this PR
    audit_rows = db.execute(
        select(AuditLog)
        .where(AuditLog.target.like(f"%{pr.repo}#{pr.number}%") | AuditLog.target.like(f"finding:%"))
        .order_by(AuditLog.timestamp)
        .limit(50)
    ).scalars().all()

    # Try LLM-narrated brief; fall back to deterministic template on any error
    narrative = await _llm_brief_narrative(pr, findings, risk) if settings.databricks_token else None
    if not narrative:
        narrative = _deterministic_brief_narrative(pr, findings, risk)

    files_block = pr.diff_text or "_(diff not stored)_"
    if len(files_block) > 1500:
        files_block = files_block[:1500] + "\n…(truncated)"

    md = f"""# Change Brief · PR #{pr.number} · `{pr.repo}`

| | |
|---|---|
| **Title** | {pr.title} |
| **Author** | {pr.author} |
| **Branch** | `{pr.branch}` → `{pr.repo.split('/')[-1]}` default |
| **Owning team** | {team_label} |
| **Files changed** | {pr.files_changed} (+{pr.additions} / -{pr.deletions}) |
| **Atlas verdict** | `{pr.verdict or pr.review_state}` |
| **Risk classification** | **{risk.upper()}** |
| **Brief generated** | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} |

---

{narrative}

---

## Findings summary

| Severity | Caught | Accepted | Dismissed | Auto-posted |
|----------|-------:|---------:|----------:|------------:|
| BLOCKER | {len(blockers)} | {sum(1 for f in blockers if f in accepted)} | {sum(1 for f in blockers if f in dismissed)} | {sum(1 for f in blockers if f.auto_posted)} |
| MAJOR   | {len(majors)} | {sum(1 for f in majors if f in accepted)} | {sum(1 for f in majors if f in dismissed)} | {sum(1 for f in majors if f.auto_posted)} |
| MINOR   | {sum(1 for f in findings if f.severity == 'MINOR')} | – | – | – |
| NIT     | {sum(1 for f in findings if f.severity == 'NIT')} | – | – | – |

## Approvers (triage decisions)
{', '.join(f'`{a}`' for a in approvers) if approvers else '_(no human decisions logged yet)_'}

## Rollback procedure
1. `git revert {pr.sha[:10]}` on the default branch (`{pr.branch}` parent).
2. Verify CI on the revert commit (same checks as forward merge).
3. If schema changes were involved, run the inverse migration before deploy.
4. Notify {team_label} on-call rotation in the team Slack channel.

## Evidence trail · last {len(audit_rows)} events
""" + "\n".join(
        f"- `{r.timestamp.strftime('%Y-%m-%d %H:%M:%S')}` · **{r.actor}** · `{r.action}` · {r.target}"
        for r in audit_rows
    ) + f"""

## Diff scope (truncated)
```
{files_block}
```

---
*Generated by Atlas Engineering Intelligence · CAB Brief v1 · paste this into ServiceNow as a Standard Change*
"""

    return CABBriefOut(
        pr_id=pr.id,
        repo=pr.repo,
        number=pr.number,
        title=pr.title,
        generated_at=datetime.utcnow(),
        markdown=md,
        risk_level=risk,
    )


async def _llm_brief_narrative(pr: PullRequest, findings: list[Finding], risk: str) -> str | None:
    """Ask Databricks Claude for the human-readable summary + blast radius sections.
    Returns markdown or None if the call fails."""
    try:
        import litellm
        prompt_facts = (
            f"PR #{pr.number} in repo `{pr.repo}` by {pr.author}\n"
            f"Title: {pr.title}\n"
            f"Files changed: {pr.files_changed} ({pr.additions} additions / {pr.deletions} deletions)\n"
            f"Atlas verdict: {pr.verdict or pr.review_state}\n"
            f"Risk: {risk}\n"
            f"Findings: {len(findings)} total · "
            f"{sum(1 for f in findings if f.severity == 'BLOCKER')} BLOCKER · "
            f"{sum(1 for f in findings if f.severity == 'MAJOR')} MAJOR\n"
            f"Top finding files: " + ", ".join(sorted({f.file for f in findings[:5]})) + "\n"
        )
        system = (
            "You write change-management briefs for a regulated financial services org. "
            "Be concise, factual, and structure your response as exactly three markdown "
            "sections with these exact headings: ## Summary, ## Blast radius, ## Why this is safe to ship. "
            "Use bullet points. No fluff. No speculation. Cite specific file paths and finding "
            "counts from the facts. Total length under 300 words."
        )
        resp = await litellm.acompletion(
            model=f"databricks/{settings.databricks_model_serving_endpoint}",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Write the change brief sections.\n\nFacts:\n{prompt_facts}"},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        return resp.choices[0].message.content
    except Exception as exc:                                          # noqa: BLE001
        logger.warning("cab_brief.llm_unreachable", error=str(exc)[:200])
        return None


def _deterministic_brief_narrative(pr: PullRequest, findings: list[Finding], risk: str) -> str:
    """Fully-deterministic fallback so the endpoint always returns useful output."""
    top_files = sorted({f.file for f in findings})[:5]
    blockers = [f for f in findings if f.severity == "BLOCKER"]
    return f"""## Summary
This change modifies {pr.files_changed} file(s) in `{pr.repo}` ({pr.additions} additions, {pr.deletions} deletions).
Atlas reviewed it and assigned verdict `{pr.verdict or pr.review_state}`, classified at **{risk.upper()}** risk based on finding severity and diff size.

## Blast radius
- Files most affected: {', '.join(f'`{f}`' for f in top_files) if top_files else '_(no specific files flagged)_'}
- Severity distribution: {len(blockers)} BLOCKER · {sum(1 for f in findings if f.severity == 'MAJOR')} MAJOR · {sum(1 for f in findings if f.severity == 'MINOR')} MINOR
- Atlas auto-posted {sum(1 for f in findings if f.auto_posted)} comment(s); the rest required human triage.

## Why this is safe to ship
- {('All BLOCKER findings have a human decision logged.' if blockers and all(f.decision for f in blockers) else 'No BLOCKER findings outstanding.')}
- {sum(1 for f in findings if f.decision and f.decision.decision == 'accept')} finding(s) were explicitly accepted and addressed in this PR.
- {sum(1 for f in findings if f.decision and f.decision.decision == 'dismiss')} finding(s) were dismissed with reviewer rationale in the Decision Ledger.
- Rollback path is documented below.
"""


# ═════════════════════════════════════════════════════════════════
# 3 · AI Decision Ledger
# ═════════════════════════════════════════════════════════════════
class LedgerEntry(BaseModel):
    """One row in the unified timeline.
    `kind` distinguishes the event type so the frontend can pick the right icon/color."""
    id: str                            # `${kind}:${db_id}` · unique across kinds
    timestamp: datetime
    kind: str                          # finding | decision | audit | review
    actor: str                         # atlas | <user>
    title: str                         # one-line headline
    detail: str                        # markdown-ish body
    severity: str | None = None
    pr_id: int | None = None
    pr_number: int | None = None
    repo: str | None = None
    team: str | None = None
    finding_id: int | None = None
    decision: str | None = None        # accept | dismiss | reply


class LedgerPage(BaseModel):
    entries: list[LedgerEntry]
    total: int
    window_days: int
    team: str


@router.get("/ledger", response_model=LedgerPage)
def ledger(
    db: Annotated[Session, Depends(get_session)],
    team: str = Query("all"),
    days: int = Query(30, ge=1, le=365),
    decision: str | None = Query(None, description="Filter: accept | dismiss | reply"),
    q: str | None = Query(None, description="Free-text search in rule_id, title, or note"),
    limit: int = Query(100, ge=1, le=500),
) -> LedgerPage:
    """Returns a chronological merged view across findings, triage decisions, and audit events.

    This is the answer to the post-mortem question "what did Atlas say about this
    finding, and why was it dismissed?" — without leaving the platform.
    """
    since = datetime.utcnow() - timedelta(days=days)
    repo_names = _repos_for_team(db, team)

    # Resolve repo → team mapping once for labeling
    team_by_repo = {
        r.full_name: r.team
        for r in db.execute(select(Repo)).scalars().all()
    }

    entries: list[LedgerEntry] = []

    # ── Findings ────────────────────────────────────────────────
    f_stmt = (
        select(Finding, PullRequest)
        .join(PullRequest, Finding.pull_request_id == PullRequest.id)
        .where(Finding.created_at >= since)
    )
    if repo_names is not None:
        f_stmt = f_stmt.where(PullRequest.repo.in_(repo_names) if repo_names else PullRequest.repo == "__none__")
    if q:
        like = f"%{q}%"
        f_stmt = f_stmt.where((Finding.rule_id.like(like)) | (Finding.title.like(like)))
    for f, pr in db.execute(f_stmt).all():
        entries.append(LedgerEntry(
            id=f"finding:{f.id}",
            timestamp=f.created_at,
            kind="finding",
            actor="atlas",
            title=f"{f.severity} · {f.title}",
            detail=f"**Rule** `{f.rule_id}` ({f.dimension})  \n**Where** `{f.file}:{f.line}`  \n**Why** {f.why[:300]}",
            severity=f.severity,
            pr_id=pr.id,
            pr_number=pr.number,
            repo=pr.repo,
            team=team_by_repo.get(pr.repo),
            finding_id=f.id,
        ))

    # ── Decisions ───────────────────────────────────────────────
    d_stmt = (
        select(TriageDecision, Finding, PullRequest)
        .join(Finding, TriageDecision.finding_id == Finding.id)
        .join(PullRequest, Finding.pull_request_id == PullRequest.id)
        .where(TriageDecision.decided_at >= since)
    )
    if repo_names is not None:
        d_stmt = d_stmt.where(PullRequest.repo.in_(repo_names) if repo_names else PullRequest.repo == "__none__")
    if decision:
        d_stmt = d_stmt.where(TriageDecision.decision == decision)
    if q:
        like = f"%{q}%"
        d_stmt = d_stmt.where((Finding.rule_id.like(like)) | (TriageDecision.note.like(like)))
    for d, f, pr in db.execute(d_stmt).all():
        verb = {"accept": "Accepted", "dismiss": "Dismissed", "reply": "Replied to"}.get(d.decision, d.decision.title())
        entries.append(LedgerEntry(
            id=f"decision:{d.id}",
            timestamp=d.decided_at,
            kind="decision",
            actor=d.user,
            title=f"{verb} · {f.title}",
            detail=(f"**Decision** `{d.decision}` on finding `{f.rule_id}`  \n"
                    f"**Note** {d.note or '_no note_'}  \n"
                    f"**Original finding** {f.why[:200]}"),
            severity=f.severity,
            pr_id=pr.id,
            pr_number=pr.number,
            repo=pr.repo,
            team=team_by_repo.get(pr.repo),
            finding_id=f.id,
            decision=d.decision,
        ))

    # ── Audit events (excluding the ones we already covered as decisions) ──
    if not decision:  # if filtering by decision, audit events aren't useful
        a_stmt = (
            select(AuditLog)
            .where(AuditLog.timestamp >= since)
            .where(~AuditLog.action.like("triage.%"))  # decisions already covered
            .order_by(desc(AuditLog.timestamp))
            .limit(200)
        )
        for a in db.execute(a_stmt).scalars().all():
            if q and q.lower() not in (a.action + a.target + a.actor).lower():
                continue
            entries.append(LedgerEntry(
                id=f"audit:{a.id}",
                timestamp=a.timestamp,
                kind="audit",
                actor=a.actor,
                title=f"{a.action} · {a.target}",
                detail=f"```json\n{a.detail}\n```" if a.detail else "_(no detail)_",
            ))

    # Newest first, capped at limit
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return LedgerPage(
        entries=entries[:limit],
        total=len(entries),
        window_days=days,
        team=team,
    )
