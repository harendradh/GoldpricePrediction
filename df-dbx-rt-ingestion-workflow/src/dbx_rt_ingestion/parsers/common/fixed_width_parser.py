"""Fixed-width parser: positional field extraction with cast validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dbx_rt_ingestion.core.exceptions import ParserError
from dbx_rt_ingestion.parsers.base import BaseParser, parser_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


@parser_registry.register("fixed_width")
class FixedWidthParser(BaseParser):
    """Parses fixed-width payloads.

    Options:
        fields: list of {name, start, length, type} — start is 1-based.
        trim:   trim extracted values (default true)
        min_length: minimum record length; shorter records are flagged.

    Field layout may come from options (self-contained spec) — a schema
    reference is not required.
    """

    def __init__(self, spec: Any) -> None:
        super().__init__(spec)
        self.fields: list[dict[str, Any]] = list(self.options.get("fields", []))
        if not self.fields:
            raise ParserError(
                "fixed_width parser requires 'fields' option",
                context={"expected": "[{name, start, length, type}]"},
            )
        for field in self.fields:
            for required in ("name", "start", "length"):
                if required not in field:
                    raise ParserError(
                        f"fixed_width field entry missing '{required}'",
                        context={"field": field},
                    )

    def parse_payload(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F

        trim = bool(self.options.get("trim", True))
        min_length = int(
            self.options.get(
                "min_length",
                max(int(f["start"]) + int(f["length"]) - 1 for f in self.fields),
            )
        )

        parsed = df.withColumn("_dfx_text", self.value_as_string(df))
        parsed = self.flag_error_when(
            parsed,
            F.length("_dfx_text") < F.lit(min_length),
            f"FIXED_WIDTH_SHORT_RECORD: expected at least {min_length} chars",
        )
        for field in self.fields:
            extracted = F.substring("_dfx_text", int(field["start"]), int(field["length"]))
            if trim:
                extracted = F.trim(extracted)
            parsed = parsed.withColumn(
                str(field["name"]),
                F.when(
                    F.col("_dfx_error").isNull(),
                    extracted.cast(str(field.get("type", "string"))),
                ),
            )
        return parsed.drop("_dfx_text")
