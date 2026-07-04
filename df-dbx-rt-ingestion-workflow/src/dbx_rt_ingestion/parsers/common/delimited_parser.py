"""Delimited / CSV parser: splits ``_dfx_value`` and casts to the schema."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.parsers.base import BaseParser, parser_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@parser_registry.register("delimited")
class DelimitedParser(BaseParser):
    """Parses single-record delimited payloads.

    Options:
        delimiter: field separator (default ',')
        encoding:  payload charset (default UTF-8)
    Records with a wrong field count are flagged, not dropped.
    """

    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F

        schema = self.require_schema(ctx)
        delimiter = str(self.options.get("delimiter", ","))
        fields = schema.spark_schema.fields

        split_col = F.split(self.value_as_string(df), F.lit(delimiter).cast("string"))
        parsed = df.withColumn("_dfx_fields", split_col)
        parsed = self.flag_error_when(
            parsed,
            F.size("_dfx_fields") != F.lit(len(fields)),
            f"DELIMITED_FIELD_COUNT: expected {len(fields)} fields "
            f"({schema.subject}@{schema.version})",
        )
        for index, field in enumerate(fields):
            parsed = parsed.withColumn(
                field.name,
                F.when(
                    F.col("_dfx_error").isNull(),
                    F.col("_dfx_fields").getItem(index).cast(field.dataType),
                ),
            )
        return parsed.drop("_dfx_fields")


@parser_registry.register("csv")
class CsvParser(DelimitedParser):
    """CSV = delimited with comma default and RFC-style quoting via from_csv."""

    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F

        schema = self.require_schema(ctx)
        csv_options = {
            "sep": str(self.options.get("delimiter", ",")),
            "quote": str(self.options.get("quote", '"')),
            "mode": "PERMISSIVE",
        }
        parsed = df.withColumn(
            "_dfx_parsed",
            F.from_csv(self.value_as_string(df), schema.spark_schema.simpleString(), csv_options),
        )
        parsed = self.flag_error_when(
            parsed,
            F.col("_dfx_parsed").isNull() & F.col("_dfx_value").isNotNull(),
            f"CSV_PARSE_FAILURE: record does not match schema "
            f"{schema.subject}@{schema.version}",
        )
        return parsed.select("*", "_dfx_parsed.*").drop("_dfx_parsed")
