"""REST API · v1 · routes that back the HTML console.

Endpoints:
  GET    /api/v1/pull-requests                     Inbox · paginated list with status + team filter
  GET    /api/v1/pull-requests/{id}                One PR + findings
  POST   /api/v1/findings/{id}/triage              Accept | dismiss | reply
  POST   /api/v1/webhooks/github                   GitHub webhook
  POST   /api/v1/quick-review                      Copilot Chat path · generates spec.md
  POST   /api/v1/chat                              Context-aware Atlas Assistant
  GET    /api/v1/teams                             Team registry · drives TopBar switcher
  GET    /api/v1/scorecard                         Engineering Health Scorecard per team
  POST   /api/v1/cab-brief/{pr_id}                 CAB Brief auto-generated from PR + findings + decisions
  GET    /api/v1/ledger                            AI Decision Ledger · unified review/triage/audit timeline
  GET    /api/v1/health                            Health check
  GET    /api/v1/insights                          Dashboard KPIs
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.db.models import AuditLog, Finding, PullRequest, Repo, TriageDecision
from app.db.session import SessionLocal, get_session
from app.github.webhooks import verify_signature
from app.workers.review_job import review_pr

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1")


# ─── Schemas ───────────────────────────────────────────────────
class PRSummary(BaseModel):
    id: int
    repo: str
    number: int
    title: str
    author: str
    branch: str
    status: str
    verdict: str | None
    review_state: str
    findings_count: int
    awaiting_count: int
    auto_posted_count: int
    updated_at: datetime


class FindingOut(BaseModel):
    id: int
    rule_id: str
    pack: str
    severity: str
    dimension: str
    file: str
    line: int
    confidence: int
    title: str
    quote: str | None
    why: str
    fix: str | None
    auto_posted: bool
    decision: str | None


class PRDetail(BaseModel):
    pr: PRSummary
    findings: list[FindingOut]


class TriageIn(BaseModel):
    decision: Literal["accept", "dismiss", "reply"]
    note: str | None = None
    user: str = "unknown"


class RepoIn(BaseModel):
    full_name: str = Field(..., min_length=3, pattern=r"^[^/\s]+/[^/\s]+$")
    team: str = "unassigned"
    enabled: bool = True
    default_branch: str = "main"
    threshold_override: int | None = Field(None, ge=0, le=100)
    slack_url: str | None = None
    notes: str | None = None


class RepoPatch(BaseModel):
    team: str | None = None
    enabled: bool | None = None
    default_branch: str | None = None
    threshold_override: int | None = Field(None, ge=0, le=100)
    slack_url: str | None = None
    notes: str | None = None


class RepoOut(BaseModel):
    id: int
    full_name: str
    team: str
    enabled: bool
    default_branch: str
    threshold_override: int | None
    slack_url: str | None
    notes: str | None
    created_at: datetime
    last_event_at: datetime | None
    review_count: int
    auto_registered: bool


class WebhookConfig(BaseModel):
    url_template: str
    secret_set: bool
    events: list[str]
    auto_post_threshold: int
    block_on_blocker: bool
    run_on_draft_prs: bool


# ─── Chat assistant ──────────────────────────────────────────
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatContext(BaseModel):
    page: str | None = None                # inbox | triage | insights | scorecard | change-briefs | ledger | settings
    current_pr_id: int | None = None
    current_finding_id: int | None = None
    selected_team: str | None = None       # team filter active in the TopBar at request time


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=40)
    context: ChatContext = ChatContext()


class ChatOut(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class QuickReviewIn(BaseModel):
    review_id: str = Field(..., min_length=1, max_length=80)
    title: str
    files: list[str]
    languages: list[str]
    context: str = ""
    priorities: dict[str, str] = Field(default_factory=dict)


class QuickReviewOut(BaseModel):
    spec_path: str
    invocation: str


# ─── Health ────────────────────────────────────────────────────
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "atlas-tier3"}


# ─── Inbox ────────────────────────────────────────────────────
@router.get("/pull-requests", response_model=list[PRSummary])
def list_prs(
    db: Annotated[Session, Depends(get_session)],
    status: str = Query("open", description="open|merged|closed|all"),
    team: str = Query("all", description="all | ingestion | fre | pre_purposing | fsbi | pgb | unassigned"),
    limit: int = Query(50, ge=1, le=200),
) -> list[PRSummary]:
    stmt = select(PullRequest).order_by(desc(PullRequest.updated_at)).limit(limit)
    if status != "all":
        stmt = stmt.where(PullRequest.status == status)
    if team != "all":
        # Scope PRs to repos owned by the selected team (PullRequest.repo == Repo.full_name)
        repo_names = db.execute(select(Repo.full_name).where(Repo.team == team)).scalars().all()
        stmt = stmt.where(PullRequest.repo.in_(repo_names) if repo_names else PullRequest.repo == "__none__")
    rows = db.execute(stmt).scalars().all()
    return [_pr_to_summary(db, r) for r in rows]


@router.get("/teams")
def list_teams(db: Annotated[Session, Depends(get_session)]) -> list[dict[str, str]]:
    """Team registry · derived from distinct values of Repo.team in the DB.

    No hardcoded org-specific team names · the registry grows as repos are
    onboarded. Returns 'All teams' as the implicit aggregate plus every
    distinct team string actually in use.
    """
    rows = db.execute(select(Repo.team).distinct().where(Repo.team != "")).scalars().all()
    teams = [{"id": "all", "label": "All teams"}]
    for team_id in sorted(set(rows)):
        label = team_id.replace("_", " ").title()
        teams.append({"id": team_id, "label": label})
    return teams


@router.get("/pull-requests/{pr_id}", response_model=PRDetail)
def get_pr(pr_id: int, db: Annotated[Session, Depends(get_session)]) -> PRDetail:
    pr = db.get(PullRequest, pr_id)
    if not pr:
        raise HTTPException(404, "PR not found")
    findings = [
        FindingOut(
            id=f.id, rule_id=f.rule_id, pack=f.pack, severity=f.severity,
            dimension=f.dimension, file=f.file, line=f.line, confidence=f.confidence,
            title=f.title, quote=f.quote, why=f.why, fix=f.fix,
            auto_posted=f.auto_posted,
            decision=f.decision.decision if f.decision else None,
        )
        for f in pr.findings
    ]
    return PRDetail(pr=_pr_to_summary(db, pr), findings=findings)


# ─── Triage ───────────────────────────────────────────────────
@router.post("/findings/{finding_id}/triage")
def triage(
    finding_id: int,
    body: TriageIn,
    db: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    f = db.get(Finding, finding_id)
    if not f:
        raise HTTPException(404, "Finding not found")

    if f.decision:
        f.decision.decision = body.decision
        f.decision.note = body.note
        f.decision.user = body.user
        f.decision.decided_at = datetime.utcnow()
    else:
        f.decision = TriageDecision(
            finding_id=finding_id,
            decision=body.decision,
            note=body.note,
            user=body.user,
        )

    db.add(
        AuditLog(
            actor=body.user,
            action=f"triage.{body.decision}",
            target=f"finding:{finding_id}",
            detail={"rule": f.rule_id, "severity": f.severity},
        )
    )
    db.commit()
    return {"status": "ok"}


# ─── Insights ─────────────────────────────────────────────────
@router.get("/insights")
def insights(db: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    total = db.execute(select(func.count(PullRequest.id))).scalar() or 0
    open_ = db.execute(
        select(func.count(PullRequest.id)).where(PullRequest.status == "open")
    ).scalar() or 0
    blockers = db.execute(
        select(func.count(Finding.id)).where(Finding.severity == "BLOCKER")
    ).scalar() or 0
    auto_posted = db.execute(
        select(func.count(Finding.id)).where(Finding.auto_posted.is_(True))
    ).scalar() or 0
    findings_total = db.execute(select(func.count(Finding.id))).scalar() or 0

    # Top rules
    top_rule_rows = db.execute(
        select(Finding.rule_id, func.count(Finding.id).label("n"))
        .group_by(Finding.rule_id)
        .order_by(desc("n"))
        .limit(5)
    ).all()

    return {
        "total_prs": total,
        "open_prs": open_,
        "blockers_caught": blockers,
        "auto_posted": auto_posted,
        "findings_total": findings_total,
        "auto_post_rate": round(auto_posted / findings_total * 100, 1) if findings_total else 0.0,
        "top_rules": [{"rule_id": r.rule_id, "count": int(r.n)} for r in top_rule_rows],
    }


# ─── Repos · onboarding + per-repo config ─────────────────────
@router.get("/repos", response_model=list[RepoOut])
def list_repos(db: Annotated[Session, Depends(get_session)]) -> list[RepoOut]:
    rows = db.execute(select(Repo).order_by(desc(Repo.last_event_at), desc(Repo.created_at))).scalars().all()
    return [_repo_to_out(r) for r in rows]


@router.post("/repos", response_model=RepoOut, status_code=201)
def create_repo(body: RepoIn, db: Annotated[Session, Depends(get_session)]) -> RepoOut:
    existing = db.execute(select(Repo).where(Repo.full_name == body.full_name)).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"repo {body.full_name} already onboarded")
    row = Repo(
        full_name=body.full_name,
        enabled=body.enabled,
        default_branch=body.default_branch,
        threshold_override=body.threshold_override,
        slack_url=body.slack_url,
        notes=body.notes,
        auto_registered=False,
    )
    db.add(row)
    db.add(AuditLog(actor="user", action="repo.created", target=body.full_name, detail={"manual": True}))
    db.commit()
    db.refresh(row)
    return _repo_to_out(row)


@router.patch("/repos/{repo_id}", response_model=RepoOut)
def update_repo(
    repo_id: int, body: RepoPatch, db: Annotated[Session, Depends(get_session)]
) -> RepoOut:
    row = db.get(Repo, repo_id)
    if not row:
        raise HTTPException(404, "repo not found")
    changes: dict[str, Any] = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None or field == "enabled":
            setattr(row, field, value)
            changes[field] = value
    db.add(AuditLog(actor="user", action="repo.updated", target=row.full_name, detail=changes))
    db.commit()
    db.refresh(row)
    return _repo_to_out(row)


@router.delete("/repos/{repo_id}", status_code=204)
def delete_repo(repo_id: int, db: Annotated[Session, Depends(get_session)]) -> None:
    row = db.get(Repo, repo_id)
    if not row:
        raise HTTPException(404, "repo not found")
    full_name = row.full_name
    db.delete(row)
    db.add(AuditLog(actor="user", action="repo.deleted", target=full_name, detail={}))
    db.commit()


@router.get("/webhook-config", response_model=WebhookConfig)
def webhook_config(request: Request) -> WebhookConfig:
    """Returns the info the user needs to paste into the GitHub repo's webhook settings."""
    # Build the URL relative to the public host — best-effort · the user can edit
    base = str(request.base_url).rstrip("/")
    return WebhookConfig(
        url_template=f"{base}/api/v1/webhooks/github",
        secret_set=bool(settings.github_webhook_secret),
        events=["pull_request: opened, synchronize, reopened, ready_for_review"],
        auto_post_threshold=settings.atlas_auto_post_threshold,
        block_on_blocker=settings.atlas_block_on_blocker,
        run_on_draft_prs=settings.atlas_run_on_draft_prs,
    )


# ─── Webhook ──────────────────────────────────────────────────
@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background: BackgroundTasks,
    x_github_event: Annotated[str | None, Header()] = None,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    body = await request.body()
    if not verify_signature(body, x_hub_signature_256):
        raise HTTPException(401, "invalid signature")

    if x_github_event == "ping":
        # GitHub sends a ping when the webhook is first configured
        return {"status": "pong", "zen": (await request.json()).get("zen", "")}

    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event or "none"}

    payload = await request.json()
    action = payload.get("action")
    if action not in {"opened", "reopened", "synchronize", "ready_for_review"}:
        return {"status": "ignored", "action": action or "none"}

    pr = payload["pull_request"]
    if pr.get("draft") and not settings.atlas_run_on_draft_prs:
        return {"status": "skipped_draft"}

    repo_full = payload["repository"]["full_name"]
    number = pr["number"]

    # Auto-register the repo on first sight · "zero-touch onboarding"
    repo_row = _upsert_repo_on_webhook(repo_full, payload["repository"].get("default_branch") or "main")
    if not repo_row.enabled:
        logger.info("webhook.repo_disabled", repo=repo_full, pr=number)
        return {"status": "skipped_disabled_repo", "repo": repo_full}

    logger.info("webhook.received", repo=repo_full, pr=number, action=action)
    background.add_task(_run_review_safe, repo_full, number)
    return {"status": "queued", "repo": repo_full, "pr": number}


def _upsert_repo_on_webhook(full_name: str, default_branch: str) -> Repo:
    """Find or create a Repo row + bump counters. Uses its own session so the
    webhook handler doesn't block on the per-request session for an audit insert.
    """
    db = SessionLocal()
    try:
        row = db.execute(select(Repo).where(Repo.full_name == full_name)).scalar_one_or_none()
        if row is None:
            row = Repo(
                full_name=full_name,
                default_branch=default_branch,
                auto_registered=True,
            )
            db.add(row)
            db.add(AuditLog(actor="atlas", action="repo.auto_registered",
                            target=full_name, detail={"source": "webhook"}))
        row.last_event_at = datetime.utcnow()
        row.review_count = (row.review_count or 0) + 1
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def _repo_to_out(r: Repo) -> RepoOut:
    return RepoOut(
        id=r.id,
        full_name=r.full_name,
        team=r.team,
        enabled=r.enabled,
        default_branch=r.default_branch,
        threshold_override=r.threshold_override,
        slack_url=r.slack_url,
        notes=r.notes,
        created_at=r.created_at,
        last_event_at=r.last_event_at,
        review_count=r.review_count,
        auto_registered=r.auto_registered,
    )


async def _run_review_safe(repo: str, pr_number: int) -> None:
    try:
        await review_pr(repo, pr_number)
    except Exception:
        logger.exception("background_review.failed", repo=repo, pr=pr_number)


# ─── Chat assistant ──────────────────────────────────────────
@router.post("/chat", response_model=ChatOut)
async def chat(
    body: ChatIn,
    db: Annotated[Session, Depends(get_session)],
) -> ChatOut:
    """Context-aware code-review chat assistant.

    Uses LiteLLM directly (which is what Google ADK uses under the hood for
    non-Google models) with the OpenAI-style messages format. Cleaner for
    simple chat completions than wrapping ADK's LlmRequest object.

    Conversation history is sent each turn (caller manages it); no server-side
    session state.
    """
    from pathlib import Path
    from Agents.Core.model import DatabricksClaude, ModelCallConfig, ModelError

    # Load chat prompt from backend/prompts/chat_assistant.md (single content file).
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "chat_assistant.md"
    base_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else (
        "You are ChangePilot Assistant — a senior engineering co-pilot for the "
        "ChangePilot Studio platform. Be concise. Cite numbers, not adjectives. "
        "Markdown is OK. Decline questions outside engineering review / governance / scorecards."
    )
    # No separate rule catalog · Agents/Skills/ owns rule definitions internally.
    rules_summary = "(see /Agents/Skills/ for the registered rule namespaces)"

    # Live context · what is the user looking at right now?
    ctx_lines: list[str] = []
    page = body.context.page or ""
    team = body.context.selected_team or "all"

    if page:
        ctx_lines.append(f"- Current page: **{page}**")
    if team and team != "all":
        ctx_lines.append(f"- Active team filter: **{team}** (everything below is scoped to this team)")

    if body.context.current_pr_id:
        pr = db.get(PullRequest, body.context.current_pr_id)
        if pr:
            ctx_lines.append(
                f"- Viewing PR **#{pr.number}** \"{pr.title}\" in `{pr.repo}` "
                f"(status: {pr.status}, verdict: {pr.verdict or 'pending'}, "
                f"author: {pr.author})"
            )
    if body.context.current_finding_id:
        f = db.get(Finding, body.context.current_finding_id)
        if f:
            ctx_lines.append(
                f"- Active finding: `{f.rule_id}` at `{f.file}:{f.line}` "
                f"(severity: **{f.severity}**, confidence: {f.confidence}, "
                f"dimension: {f.dimension})\n"
                f"  - Title: {f.title}\n"
                f"  - Reason: {f.why[:200]}"
            )

    # ── Page-specific live data injection ──────────────────────
    # For Scorecard / Ledger / CAB pages, pull live numbers so the assistant
    # can cite real metrics ("right now Ingestion's blocker leakage is 43%").
    try:
        if page == "scorecard":
            from app.api.intelligence import scorecard as _scorecard_fn
            sc = _scorecard_fn(db, team=team, days=30)
            ctx_lines.append(
                f"- **Live Scorecard for {sc.team_label} (last 30d)**: "
                f"{sc.total_prs} PRs · {sc.findings_total} findings · "
                f"{sc.blockers_caught} blockers · "
                f"blocker-leakage **{sc.blocker_leakage_rate*100:.1f}%** · "
                f"dismissal **{sc.dismissal_rate*100:.0f}%** · "
                f"queue depth **{sc.queue_depth}** · "
                f"median cycle **{sc.median_cycle_time_hours}h** · "
                f"dimensions: {sc.dimension_mix}"
            )
            if sc.top_reviewers:
                ctx_lines.append(
                    "- Top reviewers: "
                    + ", ".join(f"{r['user']} ({r['decisions']} decisions)" for r in sc.top_reviewers[:3])
                )

        elif page == "change-briefs":
            # Summary of CAB-eligible PRs in the active team scope
            stmt = select(PullRequest).order_by(desc(PullRequest.updated_at)).limit(15)
            if team != "all":
                repo_names = db.execute(select(Repo.full_name).where(Repo.team == team)).scalars().all()
                stmt = stmt.where(PullRequest.repo.in_(repo_names) if repo_names else PullRequest.repo == "__none__")
            cab_prs = db.execute(stmt).scalars().all()
            blockers_outstanding = sum(
                1 for p in cab_prs
                for f in p.findings
                if f.severity == "BLOCKER" and (not f.decision or f.decision.decision != "dismiss")
            )
            ctx_lines.append(
                f"- **CAB-eligible PRs in scope**: {len(cab_prs)} · "
                f"{blockers_outstanding} outstanding BLOCKER finding(s) across them. "
                f"Each PR can be turned into a ServiceNow-ready brief with one click."
            )

        elif page == "ledger":
            from app.api.intelligence import ledger as _ledger_fn
            led = _ledger_fn(db, team=team, days=30, decision=None, q=None, limit=20)
            dismiss_count = sum(1 for e in led.entries if e.kind == "decision" and e.decision == "dismiss")
            accept_count  = sum(1 for e in led.entries if e.kind == "decision" and e.decision == "accept")
            finding_count = sum(1 for e in led.entries if e.kind == "finding")
            ctx_lines.append(
                f"- **Live Ledger (last 30d, top 20 events)**: "
                f"{finding_count} findings · {accept_count} accepts · {dismiss_count} dismissals shown. "
                f"Total events in window: {led.total}. "
                f"User can filter by decision type and free-text search dismissal notes."
            )
    except Exception as exc:                                          # noqa: BLE001
        # Never break chat if a live-data lookup fails · just log and continue
        logger.warning("chat.context_injection_failed", page=page, error=str(exc)[:200])

    system = base_prompt + "\n\n## Skill namespaces\n" + rules_summary
    if ctx_lines:
        system += "\n\n## Current user context\n" + "\n".join(ctx_lines)

    # Build conversation for the platform's model adapter
    conversation = [{"role": m.role, "content": m.content} for m in body.messages[:-1]]
    last_user = body.messages[-1].content if body.messages else ""

    model = DatabricksClaude()
    try:
        resp = await model.complete(
            system=system, user=last_user,
            conversation=conversation,
            config=ModelCallConfig(temperature=0.3, max_tokens=1024),
        )
        return ChatOut(content=resp.content or "_(Empty response from the model.)_")
    except ModelError as exc:
        logger.error("chat.llm_error", error=str(exc)[:300])
        return ChatOut(content=(
            "I couldn't reach the Databricks Claude endpoint. "
            "Verify `DATABRICKS_HOST` and `DATABRICKS_TOKEN` in `backend/.env`."
        ))


# ─── Quick Review (Copilot Chat) ──────────────────────────────
@router.post("/quick-review", response_model=QuickReviewOut)
def quick_review(body: QuickReviewIn) -> QuickReviewOut:
    """Write a spec.md the user can paste into Copilot Chat with the agent prompt.

    The Copilot Chat path is preserved for pre-commit local checks — Atlas backend
    never runs an LLM here, just generates the spec file and the invocation string.
    """
    spec_dir = settings.specs_path / body.review_id
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_md = _render_spec_md(body)
    spec_path = spec_dir / "spec.md"
    spec_path.write_text(spec_md, encoding="utf-8")

    invocation = (
        f"#file:prompts/critic.md  #file:{spec_path.as_posix()}\n\n"
        f"Run atlas_critic on my review spec"
    )

    return QuickReviewOut(spec_path=str(spec_path), invocation=invocation)


def _render_spec_md(body: QuickReviewIn) -> str:
    pri_lines = "\n".join(
        f"- {k}: {v}" for k, v in (body.priorities or {}).items()
    ) or "- (none provided)"
    files_lines = "\n".join(f"- {f}" for f in body.files) or "- (none provided)"
    langs_lines = "\n".join(f"- {l}" for l in body.languages) or "- (none provided)"
    return f"""# Review: {body.title or body.review_id}

**Review ID:** `{body.review_id}`

## Diff scope
{files_lines}

## Languages
{langs_lines}

## Business context
{body.context or '_(none provided)_'}

## Reviewer priorities
{pri_lines}

---
_Atlas Tier-3 · Quick Review spec generated by the backend_
"""


# ─── helpers ───────────────────────────────────────────────────
def _pr_to_summary(db: Session, pr: PullRequest) -> PRSummary:
    counts = db.execute(
        select(
            func.count(Finding.id).label("total"),
            func.sum((Finding.decision == None).cast(__import__("sqlalchemy").Integer)).label("awaiting"),  # type: ignore
            func.sum(Finding.auto_posted.cast(__import__("sqlalchemy").Integer)).label("auto"),
        )
        .where(Finding.pull_request_id == pr.id)
    ).first()
    return PRSummary(
        id=pr.id,
        repo=pr.repo,
        number=pr.number,
        title=pr.title,
        author=pr.author,
        branch=pr.branch,
        status=pr.status,
        verdict=pr.verdict,
        review_state=pr.review_state,
        findings_count=int(counts.total or 0) if counts else 0,
        awaiting_count=int(counts.awaiting or 0) if counts else 0,
        auto_posted_count=int(counts.auto or 0) if counts else 0,
        updated_at=pr.updated_at,
    )
