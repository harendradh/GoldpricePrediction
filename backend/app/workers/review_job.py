"""Review job · thin wrapper around Agents.MasterAgent.

Used by:
  · FastAPI BackgroundTasks (GitHub webhook handler)
  · The /review/{pr_id} on-demand endpoint
  · Any external job runner (Databricks Workflow / cron)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.models import AuditLog, Finding, PullRequest
from app.db.session import SessionLocal

logger = get_logger(__name__)


async def review_pr(repo: str, pr_number: int) -> None:
    """Run the master agent against a PR row + persist the findings."""
    db = SessionLocal()
    try:
        pr = db.execute(
            select(PullRequest)
            .where(PullRequest.repo == repo, PullRequest.number == pr_number)
            .order_by(PullRequest.id.desc())
        ).scalars().first()
        if pr is None:
            logger.warning("review.pr_not_found", repo=repo, pr=pr_number)
            return

        pr.review_state = "running"
        db.commit()

        # Delegate to MasterAgent
        from Agents import MasterAgent
        agent = MasterAgent()
        result = await agent.review_pr(
            pr_id=pr.id,
            repo=pr.repo,
            pr_number=pr.number,
            title=pr.title,
            description="",
            author=pr.author,
            branch=pr.branch,
            base_branch="main",
            diff_text=pr.diff_text or "",
        )

        # Persist findings
        for f_payload in result.get("findings", []):
            try:
                sev = str(f_payload.get("severity", "MINOR")).upper()
                sev_order = {"BLOCKER": 1, "MAJOR": 2, "MINOR": 3, "NIT": 4}.get(sev, 99)
                db.add(Finding(
                    pull_request_id=pr.id,
                    rule_id=str(f_payload.get("rule_id", ""))[:120],
                    pack=str(f_payload.get("rule_id", "")).split(".")[0] or "general",
                    severity=sev,
                    severity_order=sev_order,
                    dimension=str(f_payload.get("dimension", "correctness")),
                    file=str(f_payload.get("file", ""))[:500],
                    line=int(f_payload.get("line_start", 0) or 0),
                    confidence=int(f_payload.get("confidence", 50)),
                    title=str(f_payload.get("title", ""))[:500],
                    quote=f_payload.get("quote"),
                    why=str(f_payload.get("why", "")),
                    fix=f_payload.get("fix"),
                    auto_posted=bool(f_payload.get("auto_postable", False)),
                    created_at=datetime.utcnow(),
                ))
            except (ValueError, TypeError, KeyError) as exc:
                logger.warning("review.persist_skip", error=str(exc)[:200])

        pr.verdict = result.get("verdict")
        pr.review_state = "done"
        pr.reviewed_at = datetime.utcnow()

        db.add(AuditLog(
            actor="master_agent",
            action="review.complete",
            target=f"pr:{pr.id}",
            detail={
                "verdict": result.get("verdict"),
                "findings_count": result.get("findings_count", 0),
                "cost_usd": (result.get("telemetry") or {}).get("estimated_cost_usd", 0),
            },
        ))
        db.commit()
        logger.info("review.persisted",
                    pr=pr_number, findings=result.get("findings_count"),
                    verdict=result.get("verdict"))
    except Exception:
        logger.exception("review.failed", repo=repo, pr=pr_number)
        db.rollback()
    finally:
        db.close()
