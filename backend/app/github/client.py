"""Thin GitHub client wrapper · PR diff fetching + inline comment posting.

POC uses a Personal Access Token. Production should switch to a GitHub App
(installation token rotation, finer scope, audit). The function signatures
here are App-ready · only the auth header changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

GH_API = "https://api.github.com"


@dataclass(slots=True)
class PRFiles:
    diff_text: str
    files: list[tuple[str, str]]            # [(path, content), ...]
    title: str
    body: str
    author: str
    branch: str
    base_sha: str
    head_sha: str
    additions: int
    deletions: int
    changed_files: int


class GitHubError(Exception):
    pass


def _headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {settings.github_token}",
        "User-Agent": "atlas-tier3/0.1",
    }


async def fetch_pr_context(repo: str, pr_number: int) -> PRFiles:
    """Pull everything Atlas needs to review a PR in one shot.

    Two API calls + N raw-content downloads (one per changed file in the diff).
    """
    async with httpx.AsyncClient(headers=_headers(), timeout=30) as client:
        # 1. PR metadata
        pr = await _get(client, f"/repos/{repo}/pulls/{pr_number}")
        # 2. Changed files
        files_meta = await _get(client, f"/repos/{repo}/pulls/{pr_number}/files?per_page=100")

        head_sha = pr["head"]["sha"]
        diff_text = await _fetch_diff(client, repo, pr_number)

        # 3. Pull each file's content at head_sha (skip removed files)
        files: list[tuple[str, str]] = []
        for f in files_meta:
            if f.get("status") == "removed":
                continue
            path = f["filename"]
            try:
                content = await _fetch_file_content(client, repo, path, head_sha)
                files.append((path, content))
            except GitHubError as exc:
                logger.warning("github.file_fetch_failed", path=path, err=str(exc))

        return PRFiles(
            diff_text=diff_text,
            files=files,
            title=pr["title"],
            body=pr.get("body") or "",
            author=pr["user"]["login"],
            branch=pr["head"]["ref"],
            base_sha=pr["base"]["sha"],
            head_sha=head_sha,
            additions=pr["additions"],
            deletions=pr["deletions"],
            changed_files=pr["changed_files"],
        )


async def post_inline_comment(
    *,
    repo: str,
    pr_number: int,
    commit_sha: str,
    path: str,
    line: int,
    body: str,
) -> int | None:
    """Post a single inline review comment · returns the comment ID.

    Uses GitHub's `POST /repos/{repo}/pulls/{n}/comments` endpoint, which
    supports `line` + `side=RIGHT` for new code (added lines).

    Failures are logged + swallowed: Tier 3 will not crash a review because
    one comment couldn't be posted (could be wrong line, file outside diff,
    etc.). The finding stays in the DB for the human triage queue.
    """
    payload = {
        "body": body,
        "commit_id": commit_sha,
        "path": path,
        "line": max(1, line),
        "side": "RIGHT",
    }
    async with httpx.AsyncClient(headers=_headers(), timeout=15) as client:
        resp = await client.post(f"{GH_API}/repos/{repo}/pulls/{pr_number}/comments", json=payload)
        if resp.status_code >= 300:
            logger.warning(
                "github.inline_comment_failed",
                repo=repo,
                pr=pr_number,
                path=path,
                line=line,
                status=resp.status_code,
                body=resp.text[:200],
            )
            return None
        return resp.json().get("id")


async def post_pr_summary(repo: str, pr_number: int, body: str) -> None:
    """Post the review summary as a regular PR-level issue comment."""
    async with httpx.AsyncClient(headers=_headers(), timeout=15) as client:
        await client.post(
            f"{GH_API}/repos/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )


# ─── helpers ───────────────────────────────────────────────────
async def _get(client: httpx.AsyncClient, path: str) -> Any:
    r = await client.get(GH_API + path)
    if r.status_code >= 300:
        raise GitHubError(f"GET {path} → {r.status_code} · {r.text[:200]}")
    return r.json()


async def _fetch_diff(client: httpx.AsyncClient, repo: str, pr_number: int) -> str:
    """Pull the unified diff via the v3.diff media type."""
    headers = {**_headers(), "Accept": "application/vnd.github.v3.diff"}
    r = await client.get(f"{GH_API}/repos/{repo}/pulls/{pr_number}", headers=headers)
    if r.status_code >= 300:
        raise GitHubError(f"diff fetch → {r.status_code}")
    return r.text


async def _fetch_file_content(client: httpx.AsyncClient, repo: str, path: str, sha: str) -> str:
    r = await client.get(f"{GH_API}/repos/{repo}/contents/{path}?ref={sha}")
    if r.status_code >= 300:
        raise GitHubError(f"file fetch → {r.status_code}")
    data = r.json()
    if isinstance(data, list):
        raise GitHubError("path is a directory")
    import base64

    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return data.get("content", "")
