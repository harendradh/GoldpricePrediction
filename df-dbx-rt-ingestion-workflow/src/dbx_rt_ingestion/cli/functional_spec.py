"""Functional specification parsing.

A functional spec is the ONE document an application team writes: a markdown
file under ``specs/<domain>/`` with a structured YAML front-matter block
(machine contract) followed by free prose (business context for humans and
AI assistants). ``dfx job add`` consumes the front matter; Copilot and
reviewers consume the prose.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dbx_rt_ingestion.core.exceptions import SpecValidationError

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


class _FnModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FieldDef(_FnModel):
    """One field of the source payload (drives the generated schema DDL)."""

    name: str
    type: str = "string"
    nullable: bool = True
    description: str = ""


class MappingDef(_FnModel):
    """One target-column mapping (drives the generated mapping file)."""

    target: str
    source: str | None = None
    expr: str | None = None
    type: str | None = None
    default: Any | None = None
    description: str = ""


class QualityDef(_FnModel):
    name: str
    type: Literal["not_null", "regex", "range", "allowed_values", "expression"]
    column: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    action: Literal["dlq", "drop", "warn", "fail"] = "dlq"


class TopicDef(_FnModel):
    name: str
    format: str = Field(description="Parser registry type: json, avro, csv, "
                                    "fixed_width, or a platform parser name.")
    schema_subject: str
    fields: list[FieldDef] = Field(default_factory=list)
    mapping: list[MappingDef] = Field(default_factory=list)
    quality: list[QualityDef] = Field(default_factory=list)
    parser_options: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)


class SourceDef(_FnModel):
    type: str = "kafka_msk"
    cluster: str = "msk-primary"
    options: dict[str, str] = Field(default_factory=dict)


class SinkDef(_FnModel):
    catalog: str
    schema_name: str = Field(alias="schema")
    table: str
    mode: Literal["append", "merge"] = "append"
    merge_keys: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @property
    def full_table(self) -> str:
        return f"{self.catalog}.{self.schema_name}.{self.table}"


class JobDef(_FnModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9\-_]{2,62}$")
    domain: str
    platform: str
    description: str = ""


class FunctionalSpec(_FnModel):
    """The machine-readable contract inside a functional spec document."""

    job: JobDef
    source: SourceDef = Field(default_factory=SourceDef)
    topics: list[TopicDef]
    sink: SinkDef
    trigger: dict[str, str] = Field(
        default_factory=lambda: {"processingTime": "30 seconds"}
    )
    tags: dict[str, str] = Field(default_factory=dict)

    @property
    def job_snake(self) -> str:
        return self.job.name.replace("-", "_")


def parse_functional_spec(path: str | Path) -> FunctionalSpec:
    """Parse the YAML front matter of a functional spec markdown file."""

    path = Path(path)
    if not path.exists():
        raise SpecValidationError(f"Functional spec not found: {path}")
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise SpecValidationError(
            f"Functional spec '{path}' has no YAML front matter "
            "(expected a '---' block at the top of the file)"
        )
    try:
        data = yaml.safe_load(match.group(1))
        return FunctionalSpec.model_validate(data)
    except ValidationError as exc:
        raise SpecValidationError(
            f"Functional spec '{path}' front matter is invalid",
            context={"errors": exc.errors(include_url=False)},
            cause=exc,
        ) from exc
