"""Sink registry and shared base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.core.interfaces import Sink
from dbx_rt_ingestion.core.registry import Registry

if TYPE_CHECKING:  # pragma: no cover
    from dbx_rt_ingestion.config.models import SinkSpec
    from dbx_rt_ingestion.core.context import PipelineContext

sink_registry: Registry[Sink] = Registry("sink")


class BaseSink(Sink):
    """Shared checkpoint/trigger/naming behavior for all sinks."""

    def __init__(self, spec: SinkSpec) -> None:
        self.spec = spec

    def checkpoint_location(self, ctx: PipelineContext) -> str:
        """Stable, per-pipeline checkpoint path (never reuse across pipelines)."""

        if self.spec.checkpoint_location:
            return self.spec.checkpoint_location
        return f"{ctx.app.checkpoint_root.rstrip('/')}/{ctx.pipeline_name}"

    def trigger_kwargs(self) -> dict[str, object]:
        """Convert the spec trigger mapping into DataStreamWriter.trigger kwargs."""

        kwargs: dict[str, object] = {}
        for key, value in self.spec.trigger.items():
            kwargs[key] = value.lower() == "true" if key == "availableNow" else value
        return kwargs
