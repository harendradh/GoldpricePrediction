"""Parser base class and registry.

The parse contract (see :class:`dbx_rt_ingestion.core.interfaces.Parser`):
- input DataFrame carries the framework envelope columns ``_dfx_*``;
- output must keep those columns and add business columns;
- malformed records must NOT fail the stream — set ``_dfx_error`` instead so
  the pipeline routes them to the DLQ.

Subclasses implement :meth:`parse_payload` only; the envelope plumbing and
error convention live here (template method).
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from dbx_rt_ingestion.core.exceptions import ParserError
from dbx_rt_ingestion.core.interfaces import Parser
from dbx_rt_ingestion.core.registry import Registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import Column, DataFrame

    from dbx_rt_ingestion.config.models import ParserSpec
    from dbx_rt_ingestion.core.context import PipelineContext

parser_registry: Registry[Parser] = Registry("parser")

#: framework envelope columns every parser must preserve
ENVELOPE_COLUMNS = (
    "_dfx_key",
    "_dfx_value",
    "_dfx_topic",
    "_dfx_partition",
    "_dfx_offset",
    "_dfx_kafka_timestamp",
    "_dfx_ingest_timestamp",
    "_dfx_error",
)


class BaseParser(Parser):
    """Template-method base for all parsers."""

    def __init__(self, spec: ParserSpec) -> None:
        self.spec = spec
        self.options: dict[str, Any] = dict(spec.options)

    # ------------------------------------------------------------------ hooks
    @abstractmethod
    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        """Parse ``_dfx_value`` into business columns; set ``_dfx_error`` on failure."""

    # --------------------------------------------------------------- template
    def parse(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        parsed = self.parse_payload(df, ctx)
        missing = [c for c in ENVELOPE_COLUMNS if c not in parsed.columns]
        if missing:
            raise ParserError(
                f"Parser '{self.spec.type}' dropped envelope columns",
                context={"missing": missing, "parser": type(self).__name__},
            )
        return parsed

    # ---------------------------------------------------------------- helpers
    def value_as_string(self, df: DataFrame) -> Column:
        """``_dfx_value`` decoded as UTF-8 string."""

        from pyspark.sql import functions as F

        encoding = str(self.options.get("encoding", "UTF-8"))
        return F.decode(F.col("_dfx_value"), encoding)

    def require_schema(self, ctx: PipelineContext) -> Any:
        """Return the resolved schema or raise a configuration-grade error."""

        if ctx.schema is None:
            raise ParserError(
                f"Parser '{self.spec.type}' requires a schema but the topic "
                "spec has none",
                context={"topic": ctx.topic.name if ctx.topic else None},
            )
        return ctx.schema

    @staticmethod
    def flag_error_when(df: DataFrame, condition: Column, message: str) -> DataFrame:
        """Set ``_dfx_error`` where ``condition`` holds (keeps existing errors)."""

        from pyspark.sql import functions as F

        return df.withColumn(
            "_dfx_error",
            F.when(F.col("_dfx_error").isNotNull(), F.col("_dfx_error"))
            .when(condition, F.lit(message))
            .otherwise(F.lit(None).cast("string")),
        )
