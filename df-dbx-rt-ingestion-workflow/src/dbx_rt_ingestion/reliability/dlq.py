"""Dead Letter Queue.

Records flagged by parsers or quality rules (``_dfx_error`` set) are split off
the main stream and written to a Delta DLQ table with full provenance (topic,
partition, offset, raw payload) so they can be inspected, fixed, and replayed.

Replay: `replay_statement` produces the SQL used by operations to re-emit
dead letters after a fix (see the operations runbook).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.core.exceptions import ConfigurationError

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame
    from pyspark.sql.streaming import StreamingQuery

    from dbx_rt_ingestion.core.context import PipelineContext


class DeadLetterQueue:
    """Streams poison records to the configured DLQ Delta table."""

    def __init__(self, ctx: PipelineContext) -> None:
        self.ctx = ctx
        self.spec = ctx.app.reliability.dlq

    @property
    def table(self) -> str:
        if self.spec.table:
            return self.spec.table
        if self.ctx.app.sink.table:
            return f"{self.ctx.app.sink.table}_dlq"
        raise ConfigurationError(
            "DLQ table cannot be derived; set reliability.dlq.table",
            context={"app": self.ctx.app.name},
        )

    @staticmethod
    def split(df: DataFrame) -> tuple[DataFrame, DataFrame]:
        """Return (valid, dead) streams based on ``_dfx_error``."""

        from pyspark.sql import functions as F

        return (
            df.filter(F.col("_dfx_error").isNull()),
            df.filter(F.col("_dfx_error").isNotNull()),
        )

    def write(self, dead: DataFrame) -> StreamingQuery:
        """Start the DLQ stream (its own checkpoint, append-only)."""

        from pyspark.sql import functions as F

        columns = [
            F.col("_dfx_error").alias("error"),
            F.col("_dfx_topic").alias("topic"),
            F.col("_dfx_partition").alias("partition"),
            F.col("_dfx_offset").alias("offset"),
            F.col("_dfx_key").alias("key"),
            F.col("_dfx_kafka_timestamp").alias("source_timestamp"),
            F.col("_dfx_ingest_timestamp").alias("ingest_timestamp"),
            F.lit(self.ctx.app.name).alias("app_name"),
            F.lit(self.ctx.run_id).alias("run_id"),
        ]
        if self.spec.include_payload:
            columns.insert(5, F.col("_dfx_value").alias("payload"))

        checkpoint = (
            f"{self.ctx.app.checkpoint_root.rstrip('/')}/"
            f"{self.ctx.pipeline_name}__dlq"
        )
        return (
            dead.select(*columns)
            .writeStream.queryName(f"{self.ctx.pipeline_name}__dlq")
            .format("delta")
            .outputMode("append")
            .option("checkpointLocation", checkpoint)
            .toTable(self.table)
        )

    def replay_statement(self) -> str:
        """SQL selecting dead letters in replayable form (ops tooling input)."""

        return (
            f"SELECT topic, partition, offset, key, payload, error "  # noqa: S608
            f"FROM {self.table} WHERE app_name = '{self.ctx.app.name}' "
            f"ORDER BY ingest_timestamp"
        )
