"""ChangePilot Studio · FastAPI entry point.

Thin wrapper that exposes REST endpoints + delegates all agent logic to
the `Agents` package at the project root.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Make the project root (containing the `Agents/` package) importable BEFORE
# the API modules try to import from it.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app import __version__
from app.api.intelligence import router as intelligence_router
from app.api.v1 import router as v1_router
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):                            # noqa: ANN001
    logger.info("changepilot.startup", version=__version__)
    init_db()
    # Eagerly import Agents so skill registry is populated.
    import Agents                                         # noqa: F401
    from skills.base import get_skill_registry
    logger.info("changepilot.agents_ready", skills=len(get_skill_registry().all()))
    yield
    logger.info("changepilot.shutdown")


app = FastAPI(
    title="ChangePilot Studio",
    version=__version__,
    description=(
        "ChangePilot Studio · AI-driven code review, CAB documentation, "
        "and engineering scorecards. Backend delegates all agent logic to "
        "the /Agents package."
    ),
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(v1_router)
app.include_router(intelligence_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": "changepilot-studio", "version": __version__, "docs": "/docs"}


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
