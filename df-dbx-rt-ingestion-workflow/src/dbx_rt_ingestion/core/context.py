"""Pipeline execution context.

A `PipelineContext` is created per topic-pipeline and passed to every
framework component (source, parser, sink, quality, DLQ). It is the single
place components look for runtime state — no globals, no hidden coupling.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import SparkSession

    from dbx_rt_ingestion.config.models import AppSpec, TopicSpec
    from dbx_rt_ingestion.schema.resolver import ResolvedSchema


@dataclass
class PipelineContext:
    """Everything a component needs to execute one topic pipeline."""

    spark: SparkSession
    app: AppSpec
    environment: str
    topic: TopicSpec | None = None
    schema: ResolvedSchema | None = None
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def pipeline_name(self) -> str:
        """Standardized pipeline/query name: ``<app>__<topic>``."""

        topic_part = self.topic.safe_name if self.topic else "main"
        return f"{self.app.name}__{topic_part}"

    def feature_enabled(self, flag: str, default: bool = False) -> bool:
        """Runtime feature-flag lookup from the application spec."""

        return bool(self.app.feature_flags.get(flag, default))
