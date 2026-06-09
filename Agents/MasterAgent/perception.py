"""Perception module · turns raw input into structured PRContext.

The only place in the platform that touches raw diff text. Everything
downstream consumes the typed PRContext.
"""
from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from Agents.Core.observability import get_logger, trace_span
from Agents.Core.schemas import FileChange, PRContext

logger = get_logger(__name__)

_EXT_TO_LANG = {
    ".py": "python", ".pyx": "python", ".ipynb": "python",
    ".java": "java", ".scala": "scala", ".kt": "kotlin",
    ".js": "javascript", ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript",
    ".sql": "sql", ".tf": "terraform", ".hcl": "terraform",
    ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".sh": "shell", ".ps1": "powershell", ".md": "markdown",
    ".rs": "rust", ".go": "go",
}
_TEST_HINTS = ("/tests/", "/test/", "test_", "_test.", ".test.", "__tests__", "/spec/", ".spec.")
_GENERATED_HINTS = ("_pb2.py", ".pb.go", "/generated/", "/__generated__/", "swagger.json", "openapi.json", "/dist/", "/build/")
_LOCKFILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "Cargo.lock", "go.sum", "Gemfile.lock",
}
_MIGRATION_HINTS = ("/migrations/", "/alembic/", "/db/migrations/", "/sql/migrations/")

_FILE_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+?)$")
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


class Perception:
    """Builds PRContext from PR metadata + raw diff text."""

    @trace_span("master.perception.build")
    def build(
        self,
        *,
        pr_id: int,
        repo: str,
        pr_number: int,
        title: str,
        description: str,
        author: str,
        branch: str,
        base_branch: str,
        diff_text: str,
    ) -> PRContext:
        files = self._parse_diff(diff_text)
        languages = sorted({f.language for f in files if f.language != "unknown"})
        total_adds = sum(f.additions for f in files)
        total_dels = sum(f.deletions for f in files)

        is_ws = self._is_whitespace_only(diff_text)
        is_lock = bool(files) and all(
            f.is_config and PurePosixPath(f.path).name.lower() in _LOCKFILE_NAMES
            for f in files
        )
        is_docs = bool(files) and all(f.language == "markdown" for f in files)
        is_gen = bool(files) and all(f.is_generated for f in files)

        smart_skip = False
        reason: str | None = None
        if is_ws:
            smart_skip, reason = True, "whitespace-only change"
        elif is_lock:
            smart_skip, reason = True, "lockfile-only change"
        elif is_docs and len(files) <= 3:
            smart_skip, reason = True, "docs-only change"
        elif is_gen:
            smart_skip, reason = True, "generated-code only"

        ctx = PRContext(
            pr_id=pr_id, repo=repo, pr_number=pr_number,
            title=title, description=description or "",
            author=author, branch=branch, base_branch=base_branch,
            files=files,
            languages_detected=languages,
            total_additions=total_adds,
            total_deletions=total_dels,
            files_changed=len(files),
            smart_skip_eligible=smart_skip,
            smart_skip_reason=reason,
            inferred_priorities=self._infer_priorities(title, description or ""),
        )
        logger.info("perception.built",
                    pr=pr_number, files=len(files), langs=languages,
                    smart_skip=smart_skip, reason=reason)
        return ctx

    # ─── Diff parsing ──────────────────────────────────────
    def _parse_diff(self, text: str) -> list[FileChange]:
        if not text or not text.strip():
            return []
        files: list[FileChange] = []
        current_path: str | None = None
        hunks: list[dict[str, Any]] = []
        adds = dels = 0
        current_hunk: dict[str, Any] | None = None

        def flush() -> None:
            nonlocal adds, dels, hunks, current_hunk
            if current_path is None:
                return
            if current_hunk:
                hunks.append(current_hunk)
            files.append(self._classify(current_path, adds, dels, hunks))
            adds = dels = 0
            hunks = []
            current_hunk = None

        for line in text.splitlines():
            m = _FILE_HEADER.match(line)
            if m:
                flush()
                current_path = m.group(2)
                continue
            m2 = _HUNK_HEADER.match(line)
            if m2:
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = {
                    "old_start": int(m2.group(1)),
                    "new_start": int(m2.group(3)),
                    "lines": [],
                }
                continue
            if current_hunk is None or current_path is None:
                continue
            if line.startswith("+") and not line.startswith("+++"):
                adds += 1
                current_hunk["lines"].append(line)
            elif line.startswith("-") and not line.startswith("---"):
                dels += 1
                current_hunk["lines"].append(line)
            elif line.startswith(" "):
                current_hunk["lines"].append(line)
        flush()
        return files

    @staticmethod
    def _classify(path: str, adds: int, dels: int, hunks: list[dict[str, Any]]) -> FileChange:
        ext = PurePosixPath(path).suffix.lower()
        language = _EXT_TO_LANG.get(ext, "unknown")
        is_test = any(h in path for h in _TEST_HINTS)
        is_gen = any(h in path for h in _GENERATED_HINTS)
        name = PurePosixPath(path).name
        is_config = (name.lower() in _LOCKFILE_NAMES
                     or ext in {".yaml", ".yml", ".json", ".toml", ".ini"})
        is_migration = any(h in path for h in _MIGRATION_HINTS)
        return FileChange(
            path=path, language=language,
            additions=adds, deletions=dels,
            is_test_file=is_test, is_generated=is_gen,
            is_config=is_config, is_migration=is_migration,
            hunks=hunks,
        )

    @staticmethod
    def _is_whitespace_only(text: str) -> bool:
        adds, dels = [], []
        for line in text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                adds.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                dels.append(line[1:])
        if not adds and not dels:
            return False
        norm = lambda xs: sorted("".join(s.split()) for s in xs)
        return norm(adds) == norm(dels)

    @staticmethod
    def _infer_priorities(title: str, description: str) -> dict[str, str]:
        text = f"{title} {description}".lower()
        prio: dict[str, str] = {}
        if any(w in text for w in ("hotfix", "security", "vulnerability", "cve")):
            prio["security"] = "MAJOR"
        if any(w in text for w in ("perf", "optim", "slow", "shuffle", "skew")):
            prio["performance"] = "MAJOR"
        if any(w in text for w in ("schema", "migration", "ddl", "breaking")):
            prio["architecture"] = "MAJOR"
            prio["data_model"] = "MAJOR"
        if any(w in text for w in ("test", "coverage", "flaky")):
            prio["testing"] = "MAJOR"
        return prio
