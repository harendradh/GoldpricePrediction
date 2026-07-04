"""Text parser: payload as a single string column (no structure)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.parsers.base import BaseParser, parser_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@parser_registry.register("text")
class TextParser(BaseParser):
    """Exposes the payload as one string column.

    Options:
        column:   output column name (default 'text')
        encoding: payload charset (default UTF-8)
    """

    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        column = str(self.options.get("column", "text"))
        return df.withColumn(column, self.value_as_string(df))
