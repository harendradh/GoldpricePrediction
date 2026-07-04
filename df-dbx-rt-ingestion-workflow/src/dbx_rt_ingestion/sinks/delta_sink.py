"""Delta Lake sink: append (native writeStream) or merge (foreachBatch upsert).

Exactly-once:
- append: Delta's transactional writeStream + per-pipeline checkpoint.
- merge:  MERGE keyed on ``merge_keys`` is idempotent under batch replay, so
  reprocessing after failure cannot duplicate rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.core.exceptions import SinkError
from dbx_rt_ingestion.sinks.base import BaseSink, sink_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@sink_registry.register("delta")
class DeltaSink(BaseSink):
    """Writes to a Unity Catalog table (``table``) or path (``path``)."""

    def write(self, df: DataFrame, ctx: PipelineContext):  # noqa: ANN201
        writer = (
            df.writeStream.queryName(ctx.pipeline_name)
            .format("delta")
            .outputMode("append")
            .option("checkpointLocation", self.checkpoint_location(ctx))
            .options(**self.spec.options)
            .trigger(**self.trigger_kwargs())
        )

        if self.spec.mode == "merge":
            return writer.foreachBatch(self._merge_batch(ctx)).start()
        if self.spec.table:
            return writer.toTable(self.spec.table)
        if self.spec.path:
            return writer.start(self.spec.path)
        raise SinkError("delta sink requires 'table' or 'path'")

    def _merge_batch(self, ctx: PipelineContext):  # noqa: ANN202
        table = self.spec.table
        keys = self.spec.merge_keys
        if not table:
            raise SinkError("merge mode requires a 'table' target")

        def merge(batch_df: DataFrame, batch_id: int) -> None:
            from delta.tables import DeltaTable

            spark = batch_df.sparkSession
            deduped = batch_df.dropDuplicates(keys)
            if not spark.catalog.tableExists(table):
                deduped.write.format("delta").saveAsTable(table)
                return
            target = DeltaTable.forName(spark, table)
            condition = " AND ".join(f"t.{k} <=> s.{k}" for k in keys)
            (
                target.alias("t")
                .merge(deduped.alias("s"), condition)
                .whenMatchedUpdateAll()
                .whenNotMatchedInsertAll()
                .execute()
            )

        return merge
