"""Declarative data-quality rules compiled to Spark expressions.

Rules run after parsing. A failing rule either:
    dlq   -> sets ``_dfx_error`` so the record routes to the DLQ (default)
    drop  -> silently removes the record
    warn  -> keeps the record, tags ``_dfx_quality_warnings``
    fail  -> configuration error at compile time is preferred; at runtime
             'fail' behaves like dlq but operations alert on the rule name.

Rule types: not_null, regex, range, allowed_values, expression.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.config.models import QualityRuleSpec
from dbx_rt_ingestion.core.exceptions import QualityError

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import Column, DataFrame


def _violation_condition(rule: QualityRuleSpec) -> Column:
    """Return a Column that is TRUE when the rule is VIOLATED."""

    from pyspark.sql import functions as F

    if rule.type == "expression":
        expression = rule.options.get("expr")
        if not expression:
            raise QualityError(f"rule '{rule.name}': expression rules require options.expr")
        return ~F.expr(str(expression))

    if rule.column is None:
        raise QualityError(f"rule '{rule.name}': '{rule.type}' requires 'column'")
    column = F.col(rule.column)

    if rule.type == "not_null":
        return column.isNull()
    if rule.type == "regex":
        pattern = rule.options.get("pattern")
        if not pattern:
            raise QualityError(f"rule '{rule.name}': regex rules require options.pattern")
        return column.isNotNull() & ~column.rlike(str(pattern))
    if rule.type == "range":
        conditions = []
        if "min" in rule.options:
            conditions.append(column < F.lit(rule.options["min"]))
        if "max" in rule.options:
            conditions.append(column > F.lit(rule.options["max"]))
        if not conditions:
            raise QualityError(f"rule '{rule.name}': range rules require min and/or max")
        violated = conditions[0]
        for extra in conditions[1:]:
            violated = violated | extra
        return column.isNotNull() & violated
    if rule.type == "allowed_values":
        values = rule.options.get("values")
        if not values:
            raise QualityError(
                f"rule '{rule.name}': allowed_values rules require options.values"
            )
        return column.isNotNull() & ~column.isin(*list(values))

    raise QualityError(f"rule '{rule.name}': unknown type '{rule.type}'")


def apply_quality_rules(df: DataFrame, rules: list[QualityRuleSpec]) -> DataFrame:
    """Apply all rules; returns the DataFrame with error/warning columns set."""

    from pyspark.sql import functions as F

    if not rules:
        return df

    result = df
    warn_flags: list[Column] = []

    for rule in rules:
        violated = _violation_condition(rule)
        message = f"QUALITY_{rule.type.upper()}:{rule.name}"

        if rule.action in ("dlq", "fail"):
            result = result.withColumn(
                "_dfx_error",
                F.when(F.col("_dfx_error").isNotNull(), F.col("_dfx_error"))
                .when(violated, F.lit(message))
                .otherwise(F.lit(None).cast("string")),
            )
        elif rule.action == "drop":
            result = result.filter(~violated | violated.isNull())
        elif rule.action == "warn":
            warn_flags.append(F.when(violated, F.lit(message)))

    if warn_flags:
        result = result.withColumn(
            "_dfx_quality_warnings",
            F.array_compact(F.array(*warn_flags)),
        )
    return result
