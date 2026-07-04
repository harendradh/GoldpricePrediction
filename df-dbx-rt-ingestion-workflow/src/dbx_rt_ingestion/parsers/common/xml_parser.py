"""XML parser: ``from_xml`` (Spark 4 / DBR 14.3+) against the topic schema."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.core.exceptions import ParserError
from dbx_rt_ingestion.parsers.base import BaseParser, parser_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@parser_registry.register("xml")
class XmlParser(BaseParser):
    """Parses XML payloads.

    Options:
        row_tag: element treated as the record root (default 'row')
    Requires DBR 14.3+ (native from_xml). On older runtimes, implement a
    platform parser using spark-xml or a UDF.
    """

    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F

        if not hasattr(F, "from_xml"):
            raise ParserError(
                "from_xml is not available on this runtime; requires DBR 14.3+/Spark 4",
            )

        schema = self.require_schema(ctx)
        xml_options = {"rowTag": str(self.options.get("row_tag", "row"))}
        parsed = df.withColumn(
            "_dfx_parsed",
            F.from_xml(self.value_as_string(df), schema.spark_schema, xml_options),
        )
        parsed = self.flag_error_when(
            parsed,
            F.col("_dfx_parsed").isNull() & F.col("_dfx_value").isNotNull(),
            f"XML_PARSE_FAILURE: document does not match {schema.subject}@{schema.version}",
        )
        return parsed.select("*", "_dfx_parsed.*").drop("_dfx_parsed")
