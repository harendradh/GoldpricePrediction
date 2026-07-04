"""Schema resolution: repository document -> Spark schema, with caching."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

from dbx_rt_ingestion.core.exceptions import SchemaError

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql.types import StructType

    from dbx_rt_ingestion.config.models import SchemaManagementSpec, SchemaRef
    from dbx_rt_ingestion.core.interfaces import SchemaRepository


@dataclass
class ResolvedSchema:
    """A schema document resolved to a concrete version."""

    subject: str
    version: str
    format: str  # ddl | json_schema | avro
    raw: str

    @cached_property
    def spark_schema(self) -> StructType:
        """The schema as a Spark StructType (lazy, cached)."""

        from pyspark.sql.types import StructType, _parse_datatype_string

        if self.format == "ddl":
            parsed = _parse_datatype_string(self.raw)
            if not isinstance(parsed, StructType):
                raise SchemaError(
                    f"DDL schema for '{self.subject}' is not a struct",
                    context={"ddl": self.raw[:200]},
                )
            return parsed

        if self.format == "json_schema":
            from dbx_rt_ingestion.schema.repository import json_schema_to_ddl_fields

            ddl = ", ".join(
                f"{name} {spark_type}"
                for name, spark_type, _nullable in json_schema_to_ddl_fields(self.raw)
            )
            return _parse_datatype_string(f"struct<{ddl}>")  # type: ignore[return-value]

        if self.format == "avro":
            # from_avro consumes the raw Avro JSON directly; a StructType view
            # is only needed for evolution checks.
            raise SchemaError(
                f"Avro schema '{self.subject}' has no StructType view; "
                "parsers should use .raw with from_avro"
            )

        raise SchemaError(f"Unknown schema format '{self.format}'")


class SchemaResolver:
    """Resolves topic schema references through the configured repository.

    Caches by (subject, version) so multi-topic apps hit the repository once
    per distinct reference. Pinned versions are immutable; 'latest' is
    resolved once at startup for run-level determinism.
    """

    def __init__(self, spec: SchemaManagementSpec) -> None:
        from dbx_rt_ingestion.schema.repository import build_schema_repository

        self._repository: SchemaRepository = build_schema_repository(
            spec.repository, dict(spec.options)
        )
        self._cache: dict[tuple[str, str], ResolvedSchema] = {}

    def resolve(self, ref: SchemaRef) -> ResolvedSchema:
        key = (ref.subject, ref.version)
        if key not in self._cache:
            resolved = self._repository.fetch(ref.subject, ref.version)
            if ref.format != resolved.format:
                raise SchemaError(
                    f"Schema '{ref.subject}@{ref.version}' has format "
                    f"'{resolved.format}' but the spec expects '{ref.format}'",
                )
            self._cache[key] = resolved
        return self._cache[key]


@dataclass
class SchemaResolutionReport:
    """Startup summary of every resolved schema (logged for auditability)."""

    entries: list[dict[str, Any]] = field(default_factory=list)

    def add(self, resolved: ResolvedSchema) -> None:
        self.entries.append(
            {
                "subject": resolved.subject,
                "version": resolved.version,
                "format": resolved.format,
            }
        )
