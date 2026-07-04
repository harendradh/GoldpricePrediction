"""Pydantic models for the application specification (the "spec").

The spec is the single source of truth for a streaming application. The YAML
layout mirrors these models exactly; field descriptions double as the spec
reference documentation.

Design rules:
- Unknown fields are rejected (``extra="forbid"``) so typos fail at startup.
- Every extensible component is addressed by a registry ``type`` string plus
  free-form ``options`` for the implementation.
- Secrets are never stored in the spec; use ``${secret:scope/key}``.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _SpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------- auth
class AuthSpec(_SpecModel):
    """Connection security. ``type`` resolves in the auth provider registry."""

    type: Literal["none", "ssl", "mtls", "sasl_ssl", "msk_iam", "kerberos"] = "none"
    options: dict[str, str] = Field(
        default_factory=dict,
        description="Provider-specific options, e.g. truststore location, "
        "sasl mechanism, principal. Values may use ${secret:scope/key}.",
    )


# ------------------------------------------------------------------------ cluster
class ClusterSpec(_SpecModel):
    """A named Kafka cluster definition (shared across applications)."""

    name: str
    provider: Literal["msk", "cloudera", "generic"] = "generic"
    bootstrap_servers: str = Field(description="Comma-separated broker list.")
    auth: AuthSpec = Field(default_factory=AuthSpec)
    options: dict[str, str] = Field(
        default_factory=dict,
        description="Cluster-level Kafka reader options (kafka.* or reader options).",
    )


# ------------------------------------------------------------------------- schema
class SchemaRef(_SpecModel):
    """Reference to a schema in the configured schema repository."""

    subject: str = Field(description="Schema subject, e.g. 'platform_a.accounts'.")
    version: str = Field(default="latest", description="Version id or 'latest'.")
    format: Literal["ddl", "json_schema", "avro"] = "ddl"
    compatibility: Literal["none", "backward", "forward", "full"] = "backward"


class SchemaManagementSpec(_SpecModel):
    """Where and how schemas are resolved for this application."""

    repository: str = Field(
        default="file", description="Schema repository registry type: file, volume, registry."
    )
    options: dict[str, str] = Field(
        default_factory=dict,
        description="Repository options, e.g. base_path or registry url.",
    )


# ------------------------------------------------------------------------- parser
class ParserSpec(_SpecModel):
    """Parser selection. ``type`` resolves in the parser registry.

    Common parsers: json, avro, csv, delimited, fixed_width, xml, text, binary.
    Platform parsers use dotted names, e.g. 'platform_a.account'.
    """

    type: str
    options: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------------ quality
class QualityRuleSpec(_SpecModel):
    """One declarative data-quality rule applied post-parse."""

    name: str
    type: Literal["not_null", "regex", "range", "allowed_values", "expression"]
    column: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    action: Literal["dlq", "drop", "warn", "fail"] = "dlq"


# --------------------------------------------------------------------------- sink
class SinkSpec(_SpecModel):
    """Sink selection. ``type`` resolves in the sink registry (delta, console...)."""

    type: str = "delta"
    table: str | None = Field(default=None, description="Unity Catalog table name.")
    path: str | None = None
    mode: Literal["append", "merge"] = "append"
    merge_keys: list[str] = Field(default_factory=list)
    checkpoint_location: str | None = Field(
        default=None,
        description="Optional override; defaults to "
        "<app.checkpoint_root>/<pipeline_name>.",
    )
    trigger: dict[str, str] = Field(
        default_factory=lambda: {"processingTime": "30 seconds"},
        description="Streaming trigger, e.g. {processingTime: '30 seconds'} or "
        "{availableNow: 'true'}.",
    )
    options: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_target(self) -> SinkSpec:
        if self.type == "delta" and not (self.table or self.path):
            raise ValueError("delta sink requires 'table' or 'path'")
        if self.mode == "merge" and not self.merge_keys:
            raise ValueError("merge mode requires 'merge_keys'")
        return self


# ------------------------------------------------------------------------ mapping
class ColumnMappingSpec(_SpecModel):
    """One target-column mapping rule (source-to-target schema mapping).

    Exactly one of ``source`` (a source column, defaults to ``target``) or
    ``expr`` (a Spark SQL expression) supplies the value.
    """

    target: str = Field(description="Output column name in the sink table.")
    source: str | None = Field(default=None, description="Source column name.")
    expr: str | None = Field(default=None, description="Spark SQL expression.")
    type: str | None = Field(default=None, description="Optional cast, e.g. decimal(18,2).")
    default: Any | None = Field(
        default=None, description="Fallback literal when the value is null."
    )
    description: str = ""

    @model_validator(mode="after")
    def _one_value_source(self) -> ColumnMappingSpec:
        if self.source and self.expr:
            raise ValueError(f"mapping '{self.target}': set 'source' or 'expr', not both")
        return self


# -------------------------------------------------------------------------- topic
class TopicSpec(_SpecModel):
    """One Kafka topic (or Auto Loader path) pipeline definition."""

    name: str
    schema_ref: SchemaRef | None = Field(default=None, alias="schema")
    parser: ParserSpec
    mapping: list[ColumnMappingSpec] = Field(
        default_factory=list,
        description="Source-to-target column mapping applied after parsing. "
        "Usually loaded from a mapping file via 'mapping_file'.",
    )
    mapping_file: str | None = Field(
        default=None,
        description="Path (project-root or conf-dir relative) to a mapping "
        "file with a top-level 'columns:' list; populated into 'mapping' at "
        "load time.",
    )
    quality: list[QualityRuleSpec] = Field(default_factory=list)
    sink: SinkSpec | None = Field(
        default=None, description="Per-topic sink override; defaults to app sink."
    )
    options: dict[str, str] = Field(
        default_factory=dict, description="Per-topic Kafka reader option overrides."
    )
    watermark: dict[str, str] | None = Field(
        default=None, description="e.g. {column: event_ts, delay: '10 minutes'}"
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @property
    def safe_name(self) -> str:
        return re.sub(r"[^A-Za-z0-9_]+", "_", self.name).strip("_").lower()


# ------------------------------------------------------------------------- source
class SourceSpec(_SpecModel):
    """Source selection. ``type`` resolves in the source registry."""

    type: str = Field(description="kafka_msk | kafka_cloudera | autoloader | ...")
    cluster: str | None = Field(
        default=None, description="Cluster name resolved from conf/clusters."
    )
    topics: list[TopicSpec] = Field(default_factory=list)
    options: dict[str, str] = Field(
        default_factory=dict,
        description="Source-level reader options, e.g. startingOffsets, "
        "maxOffsetsPerTrigger, or cloudFiles.* for autoloader.",
    )

    @model_validator(mode="after")
    def _validate(self) -> SourceSpec:
        if self.type.startswith("kafka"):
            if not self.cluster:
                raise ValueError(f"source type '{self.type}' requires 'cluster'")
            if not self.topics:
                raise ValueError(f"source type '{self.type}' requires at least one topic")
        return self


# -------------------------------------------------------------------- reliability
class RetrySpec(_SpecModel):
    max_attempts: int = Field(default=3, ge=1, le=20)
    initial_backoff_seconds: float = Field(default=5.0, ge=0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    max_backoff_seconds: float = Field(default=300.0, ge=0)


class DlqSpec(_SpecModel):
    enabled: bool = True
    table: str | None = Field(
        default=None, description="Delta table for dead letters; defaults to "
        "<sink.table>_dlq when omitted."
    )
    include_payload: bool = Field(
        default=True, description="Persist the raw record bytes alongside the error."
    )


class ReliabilitySpec(_SpecModel):
    retry: RetrySpec = Field(default_factory=RetrySpec)
    dlq: DlqSpec = Field(default_factory=DlqSpec)
    fail_fast: bool = Field(
        default=False,
        description="When true, the first pipeline failure stops the whole app "
        "instead of retrying.",
    )
    graceful_shutdown_marker: str | None = Field(
        default=None,
        description="Path checked periodically; if the file exists, queries "
        "stop after the in-flight batch (graceful shutdown).",
    )


# ------------------------------------------------------------------ observability
class PublisherSpec(_SpecModel):
    type: str = Field(description="Metrics publisher registry type: log, delta, http.")
    options: dict[str, str] = Field(default_factory=dict)


class ObservabilitySpec(_SpecModel):
    publishers: list[PublisherSpec] = Field(
        default_factory=lambda: [PublisherSpec(type="log")]
    )
    audit_table: str | None = Field(
        default=None, description="Delta table for per-batch audit records."
    )
    log_level: str = "INFO"


# ---------------------------------------------------------------------------- app
class AppSpec(_SpecModel):
    """Top-level application specification."""

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9\-_]{2,62}$")
    domain: str = Field(description="Business domain, e.g. 'gbs-auth'.")
    platform: str = Field(description="Platform id used for parser namespacing.")
    version: str = "1.0.0"
    description: str = ""
    source: SourceSpec
    sink: SinkSpec
    schema_management: SchemaManagementSpec = Field(default_factory=SchemaManagementSpec)
    reliability: ReliabilitySpec = Field(default_factory=ReliabilitySpec)
    observability: ObservabilitySpec = Field(default_factory=ObservabilitySpec)
    checkpoint_root: str = Field(
        description="Root path for checkpoints; each pipeline gets a stable "
        "subdirectory. NEVER change for a deployed app."
    )
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def _tag_keys(cls, v: dict[str, str]) -> dict[str, str]:
        for key in v:
            if not re.fullmatch(r"[A-Za-z0-9_.\-]+", key):
                raise ValueError(f"invalid tag key: {key!r}")
        return v
