"""Console sink — development and smoke-testing only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.sinks.base import BaseSink, sink_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@sink_registry.register("console")
class ConsoleSink(BaseSink):
    """Prints micro-batches to stdout. Never use in production specs."""

    def write(self, df: DataFrame, ctx: PipelineContext):  # noqa: ANN201
        return (
            df.writeStream.queryName(ctx.pipeline_name)
            .format("console")
            .option("truncate", self.spec.options.get("truncate", "true"))
            .option("numRows", self.spec.options.get("numRows", "20"))
            .option("checkpointLocation", self.checkpoint_location(ctx))
            .trigger(**self.trigger_kwargs())
            .start()
        )
