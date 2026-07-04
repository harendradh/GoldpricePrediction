"""Schema evolution / compatibility checks.

Compatibility semantics (consumer perspective):
    backward  new schema can read data written with the old schema
              (no removed fields; added fields must be nullable)
    forward   old schema can read data written with the new schema
              (no added required fields; removed fields must have been nullable)
    full      backward AND forward
    none      no check

Used by deployment tooling and optionally at startup when a topic pins
``compatibility`` in its schema reference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.core.exceptions import SchemaCompatibilityError

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql.types import StructType


def check_compatibility(
    old: StructType,
    new: StructType,
    mode: str,
    *,
    subject: str = "<unknown>",
) -> None:
    """Raise :class:`SchemaCompatibilityError` when ``new`` violates ``mode``."""

    if mode == "none":
        return

    problems: list[str] = []
    old_fields = {f.name: f for f in old.fields}
    new_fields = {f.name: f for f in new.fields}

    if mode in ("backward", "full"):
        for name, old_field in old_fields.items():
            if name not in new_fields:
                problems.append(f"backward: field '{name}' was removed")
            elif new_fields[name].dataType != old_field.dataType:
                problems.append(
                    f"backward: field '{name}' changed type "
                    f"{old_field.dataType.simpleString()} -> "
                    f"{new_fields[name].dataType.simpleString()}"
                )
        for name, new_field in new_fields.items():
            if name not in old_fields and not new_field.nullable:
                problems.append(f"backward: new field '{name}' must be nullable")

    if mode in ("forward", "full"):
        for name in new_fields:
            if name not in old_fields and not new_fields[name].nullable:
                problems.append(f"forward: added field '{name}' must be nullable")
        for name, old_field in old_fields.items():
            if name not in new_fields and not old_field.nullable:
                problems.append(
                    f"forward: removed field '{name}' was non-nullable"
                )

    if problems:
        raise SchemaCompatibilityError(
            f"Schema '{subject}' violates '{mode}' compatibility",
            context={"problems": problems},
        )
