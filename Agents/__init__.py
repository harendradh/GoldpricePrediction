"""ChangePilot AI Agent Platform.

Single source of truth for all agent code. Backend + frontend are thin
shells that route requests to / render output from this package.

Layout:
    Agents/Core/       — shared primitives (model, memory, schemas, observability)
    Agents/MasterAgent/— top-level P/R/P/A orchestrator
    Agents/SubAgents/  — 10 specialized workers
    .github/skills/    — 17 reusable skills (relocated for GitHub Copilot discovery)

Public surface:
    from Agents import MasterAgent, run_master_agent
    from Agents.SubAgents import (
        CodeReviewAgent, SecurityReviewAgent, PerformanceReviewAgent, …
    )
    from Agents.Core import DatabricksClaude, AgentMemory, Finding
    from skills.base import get_skill_registry   # after Agents is imported
"""
from __future__ import annotations

# ─── Bootstrap · make `.github/` importable so `import skills.X` works ──
# Skills live at `.github/skills/` so GitHub Copilot can auto-discover them.
# Python doesn't care about the leading-dot folder name as long as we put
# it on sys.path before anything tries to `import skills.…`.
import sys
from pathlib import Path

_GITHUB_DIR = Path(__file__).resolve().parent.parent / ".github"
if _GITHUB_DIR.is_dir() and str(_GITHUB_DIR) not in sys.path:
    sys.path.insert(0, str(_GITHUB_DIR))

# Now safe to load the rest of the package
from Agents.MasterAgent.agent import MasterAgent, run_master_agent       # noqa: E402

__all__ = ["MasterAgent", "run_master_agent"]
__version__ = "2.0.0"
