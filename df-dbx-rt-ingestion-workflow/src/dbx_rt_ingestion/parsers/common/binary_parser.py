"""Binary passthrough parser: raw bytes preserved for downstream decoding."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.parsers.base import BaseParser, parser_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@parser_registry.register("binary")
class BinaryParser(BaseParser):
    """Passes ``_dfx_value`` through untouched as ``payload`` (binary).

    Use when a downstream job or platform-specific stage owns decoding, or
    for archival ingestion of proprietary formats.

    Options:
        column: output column name (default 'payload')
    """

    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F

        column = str(self.options.get("column", "payload"))
        return df.withColumn(column, F.col("_dfx_value"))
