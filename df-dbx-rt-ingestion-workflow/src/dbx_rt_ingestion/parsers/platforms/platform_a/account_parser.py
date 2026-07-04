"""Platform A account parser — reference platform-specific implementation.

Demonstrates the recommended pattern: compose a common format parser for the
mechanical decoding, then apply platform business logic on top. Platform
parsers own their record layout so a layout change ships as a platform_a
release only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dbx_rt_ingestion.config.models import ParserSpec
from dbx_rt_ingestion.parsers.base import BaseParser, parser_registry
from dbx_rt_ingestion.parsers.common.fixed_width_parser import FixedWidthParser

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext

#: Platform A mainframe account record layout (1-based positions)
_ACCOUNT_LAYOUT: list[dict[str, Any]] = [
    {"name": "account_id", "start": 1, "length": 12, "type": "string"},
    {"name": "customer_id", "start": 13, "length": 10, "type": "string"},
    {"name": "account_type", "start": 23, "length": 2, "type": "string"},
    {"name": "status_code", "start": 25, "length": 1, "type": "string"},
    {"name": "balance_cents", "start": 26, "length": 15, "type": "long"},
    {"name": "open_date", "start": 41, "length": 8, "type": "string"},
]

_VALID_STATUS_CODES = ("A", "C", "F", "S")


@parser_registry.register("platform_a.account")
class PlatformAAccountParser(BaseParser):
    """Decodes Platform A fixed-width account records and applies business rules."""

    def __init__(self, spec: ParserSpec) -> None:
        super().__init__(spec)
        layout_options = {"fields": _ACCOUNT_LAYOUT, "trim": True, **spec.options}
        self._fixed_width = FixedWidthParser(
            ParserSpec(type="fixed_width", options=layout_options)
        )

    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F

        decoded = self._fixed_width.parse_payload(df, ctx)

        decoded = self.flag_error_when(
            decoded,
            F.col("_dfx_error").isNull()
            & ~F.col("status_code").isin(*_VALID_STATUS_CODES),
            "PLATFORM_A_INVALID_STATUS: status_code not in "
            + ",".join(_VALID_STATUS_CODES),
        )

        return (
            decoded.withColumn(
                "balance",
                (F.col("balance_cents") / F.lit(100)).cast("decimal(18,2)"),
            )
            .withColumn("open_date", F.to_date("open_date", "yyyyMMdd"))
            .withColumn("source_platform", F.lit("platform_a"))
        )
