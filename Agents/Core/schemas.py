"""Canonical Pydantic models. Every cross-module data shape lives here."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


SCHEMA_VERSION = "2.0.0"


class Severity(str, Enum):
    BLOCKER = "BLOCKER"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    NIT = "NIT"

    @property
    def order(self) -> int:
        return {"BLOCKER": 1, "MAJOR": 2, "MINOR": 3, "NIT": 4}[self.value]


class Dimension(str, Enum):
    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    DEPENDENCIES = "dependencies"
    GOVERNANCE = "governance"
    CONFIGURATION = "configuration"
    DATA_MODEL = "data_model"
    API_CONTRACT = "api_contract"
    CONCURRENCY = "concurrency"
    RESOURCE_MANAGEMENT = "resource_management"
    ERROR_HANDLING = "error_handling"


class ReviewMode(str, Enum):
    QUICK = "quick"
    DEEP = "deep"


class ReviewVerdict(str, Enum):
    MERGE = "merge"
    IMPROVE = "improve"
    BLOCK = "block"
    SMART_SKIP = "smart_skip"


class CABRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FileChange(BaseModel):
    path: str
    language: str
    additions: int
    deletions: int
    is_test_file: bool = False
    is_generated: bool = False
    is_config: bool = False
    is_migration: bool = False
    hunks: list[dict[str, Any]] = Field(default_factory=list)


class PRContext(BaseModel):
    schema_version: str = SCHEMA_VERSION
    pr_id: int
    repo: str
    pr_number: int
    title: str
    description: str = ""
    author: str
    branch: str
    base_branch: str = "main"
    files: list[FileChange] = Field(default_factory=list)
    languages_detected: list[str] = Field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0
    files_changed: int = 0
    smart_skip_eligible: bool = False
    smart_skip_reason: str | None = None
    inferred_priorities: dict[str, str] = Field(default_factory=dict)


class Finding(BaseModel):
    schema_version: str = SCHEMA_VERSION
    rule_id: str
    skill: str
    dimension: Dimension
    severity: Severity
    confidence: int = Field(..., ge=0, le=100)
    file: str
    line_start: int = 0
    line_end: int = 0
    title: str
    quote: str | None = None
    why: str
    fix: str | None = None
    references: list[str] = Field(default_factory=list)
    auto_postable: bool = False
    emitted_at: datetime = Field(default_factory=datetime.utcnow)


class CABBriefSection(BaseModel):
    section_id: str
    title: str
    body_markdown: str
    is_llm_generated: bool = True
    confidence: int = 80


class CABBrief(BaseModel):
    schema_version: str = SCHEMA_VERSION
    pr_id: int
    repo: str
    pr_number: int
    title: str
    risk_level: CABRiskLevel
    sections: list[CABBriefSection]
    full_markdown: str
    template_version: str = "v2.0"
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ScorecardMetrics(BaseModel):
    team: str
    team_label: str
    window_days: int
    total_prs: int
    open_prs: int
    findings_total: int
    findings_per_pr: float
    blockers_caught: int
    blocker_leakage_rate: float
    dismissal_rate: float
    auto_post_rate: float
    median_cycle_time_hours: float | None
    queue_depth: int
    dimension_mix: dict[str, int]
    top_reviewers: list[dict[str, Any]] = Field(default_factory=list)
    daily_findings: list[dict[str, Any]] = Field(default_factory=list)


class ScorecardSnapshot(BaseModel):
    schema_version: str = SCHEMA_VERSION
    metrics: ScorecardMetrics
    narrative_markdown: str
    health_grade: str
    risk_signals: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentRunRecord(BaseModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    agent_name: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    pr_id: int | None = None
    repo: str | None = None
    team: str | None = None
    correlation_id: str | None = None
    findings_count: int = 0
    blocker_count: int = 0
    verdict: ReviewVerdict | None = None
    sub_agents_invoked: list[str] = Field(default_factory=list)
    skills_invoked: list[str] = Field(default_factory=list)
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    error: str | None = None


class WorkflowResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    workflow: str
    success: bool
    duration_ms: int
    run_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class SkillContext(BaseModel):
    """What every Skill needs to execute."""
    pr: PRContext | None = None
    memory: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    model_config = {"arbitrary_types_allowed": True}


class SkillResult(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    fallback_used: bool = False
    duration_ms: int = 0
