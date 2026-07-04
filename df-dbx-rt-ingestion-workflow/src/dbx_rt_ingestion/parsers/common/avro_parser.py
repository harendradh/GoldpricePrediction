"""Avro parser: ``from_avro`` against the resolved Avro schema JSON."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.core.exceptions import ParserError
from dbx_rt_ingestion.parsers.base import BaseParser, parser_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@parser_registry.register("avro")
class AvroParser(BaseParser):
    """Parses Avro-encoded payloads.

    Options:
        confluent_wire_format: strip the 5-byte Confluent header (magic byte +
            schema id) before decoding (default false).
        mode: from_avro mode, PERMISSIVE (default) or FAILFAST.

    Requires a schema reference with ``format: avro`` — the raw Avro schema
    JSON is passed to ``from_avro``.
    """

    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F
        from pyspark.sql.avro.functions import from_avro

        schema = self.require_schema(ctx)
        if schema.format != "avro" or not schema.raw:
            raise ParserError(
                "avro parser requires a schema reference with format 'avro'",
                context={"subject": schema.subject, "format": schema.format},
            )

        value = F.col("_dfx_value")
        if bool(self.options.get("confluent_wire_format", False)):
            value = F.expr("substring(_dfx_value, 6, length(_dfx_value) - 5)")

        mode = str(self.options.get("mode", "PERMISSIVE"))
        parsed = df.withColumn(
            "_dfx_parsed", from_avro(value, schema.raw, {"mode": mode})
        )
        parsed = self.flag_error_when(
            parsed,
            F.col("_dfx_parsed").isNull() & F.col("_dfx_value").isNotNull(),
            f"AVRO_PARSE_FAILURE: payload does not match {schema.subject}@{schema.version}",
        )
        return parsed.select("*", "_dfx_parsed.*").drop("_dfx_parsed")
