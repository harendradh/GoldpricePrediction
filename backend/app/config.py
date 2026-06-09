"""Centralized settings · loaded from environment / .env file."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Databricks Claude (model serving) ─────────────────────
    databricks_host: str = Field(..., description="https://adb-xxxxx.azuredatabricks.net")
    databricks_token: str = Field(..., description="Workspace PAT")
    databricks_model_serving_endpoint: str = Field("databricks-claude-3-7-sonnet")
    databricks_model_fallbacks: str = Field("")

    # ── GitHub ────────────────────────────────────────────────
    github_token: str = Field(..., description="PAT for POC; switch to App for prod")
    github_webhook_secret: str = Field(...)

    # ── Persistence ───────────────────────────────────────────
    database_url: str = Field("sqlite:///./atlas.db")

    # ── Review behavior ───────────────────────────────────────
    atlas_auto_post_threshold: int = Field(80, ge=0, le=100)
    atlas_block_on_blocker: bool = Field(True)
    atlas_run_on_draft_prs: bool = Field(False)

    # ── Paths ─────────────────────────────────────────────────
    atlas_rules_dir: str = Field("./rules")
    atlas_prompts_dir: str = Field("./prompts")
    atlas_specs_dir: str = Field("./specs")

    # ── Server ────────────────────────────────────────────────
    host: str = Field("0.0.0.0")
    port: int = Field(8000)
    log_level: str = Field("INFO")

    # ── Notifications (optional) ──────────────────────────────
    slack_webhook_url: str = Field("")

    # ── Derived helpers ───────────────────────────────────────
    @property
    def fallback_models(self) -> list[str]:
        if not self.databricks_model_fallbacks:
            return []
        return [m.strip() for m in self.databricks_model_fallbacks.split(",") if m.strip()]

    @property
    def rules_path(self) -> Path:
        return Path(self.atlas_rules_dir).resolve()

    @property
    def prompts_path(self) -> Path:
        return Path(self.atlas_prompts_dir).resolve()

    @property
    def specs_path(self) -> Path:
        p = Path(self.atlas_specs_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p


# Singleton · imported by `from app.config import settings`
settings = Settings()  # type: ignore[call-arg]
