"""Databricks Auto Loader (cloudFiles) source.

For Auto Loader, ``TopicSpec.name`` carries the input path and
``TopicSpec.options`` may override cloudFiles options. The file payload is
normalized to the same ``_dfx_*`` envelope Kafka produces so parsers are
source-agnostic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.core.exceptions import SourceError
from dbx_rt_ingestion.sources.base import BaseStreamingSource, source_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@source_registry.register("autoloader")
class AutoLoaderSource(BaseStreamingSource):
    """Incremental file ingestion via cloudFiles.

    Reads files as binary and exposes content as ``_dfx_value`` so the
    configured parser owns format interpretation, exactly as with Kafka.
    """

    provider_defaults: dict[str, str] = {
        "cloudFiles.format": "binaryFile",
        "cloudFiles.inferColumnTypes": "false",
    }

    def read(self, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F

        if self.topic_spec is None:
            raise SourceError("autoloader source requires a topic entry with the input path")

        options = dict(self.provider_defaults)
        options.update(self.source_spec.options)
        options.update(self.topic_spec.options)
        path = self.topic_spec.name

        df = ctx.spark.readStream.format("cloudFiles").options(**options).load(path)

        return df.select(
            F.col("path").alias("_dfx_key"),
            F.col("content").alias("_dfx_value"),
            F.lit(path).alias("_dfx_topic"),
            F.lit(-1).cast("int").alias("_dfx_partition"),
            F.lit(-1).cast("long").alias("_dfx_offset"),
            F.col("modificationTime").alias("_dfx_kafka_timestamp"),
            F.current_timestamp().alias("_dfx_ingest_timestamp"),
            F.lit(None).cast("string").alias("_dfx_error"),
        )
