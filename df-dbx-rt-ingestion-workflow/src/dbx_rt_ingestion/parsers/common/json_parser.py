"""JSON parser: ``from_json`` against the resolved topic schema."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.parsers.base import BaseParser, parser_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@parser_registry.register("json")
class JsonParser(BaseParser):
    """Parses UTF-8 JSON payloads.

    Options:
        encoding: payload charset (default UTF-8)
        timestamp_format: passed through to from_json
    Malformed documents yield a null struct -> routed to DLQ via _dfx_error.
    """

    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F

        schema = self.require_schema(ctx)
        from_json_options = {"mode": "PERMISSIVE"}
        if "timestamp_format" in self.options:
            from_json_options["timestampFormat"] = str(self.options["timestamp_format"])

        parsed = df.withColumn(
            "_dfx_parsed",
            F.from_json(self.value_as_string(df), schema.spark_schema, from_json_options),
        )
        parsed = self.flag_error_when(
            parsed,
            F.col("_dfx_parsed").isNull() & F.col("_dfx_value").isNotNull(),
            "JSON_PARSE_FAILURE: document does not match schema "
            f"{schema.subject}@{schema.version}",
        )
        return parsed.select("*", "_dfx_parsed.*").drop("_dfx_parsed")
