"""Schema repositories: where schema documents live.

Built-in repositories:
    file      versioned files under a base directory:
                  <base_path>/<subject>/<version>.(ddl|json|avsc)
    volume    same layout on a Unity Catalog volume (alias of file)
    registry  Confluent-compatible Schema Registry over REST

Version 'latest' resolves to the highest numeric version available.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from dbx_rt_ingestion.core.exceptions import SchemaError
from dbx_rt_ingestion.core.interfaces import SchemaRepository
from dbx_rt_ingestion.core.registry import Registry
from dbx_rt_ingestion.schema.resolver import ResolvedSchema

schema_repository_registry: Registry[SchemaRepository] = Registry("schema repository")

_EXTENSION_FORMAT = {".ddl": "ddl", ".json": "json_schema", ".avsc": "avro"}


@schema_repository_registry.register("file")
class FileSchemaRepository(SchemaRepository):
    """Versioned schema files under ``options.base_path``."""

    def __init__(self, options: dict[str, str]) -> None:
        base_path = options.get("base_path")
        if not base_path:
            raise SchemaError("file schema repository requires 'base_path' option")
        self.base_path = Path(base_path)

    def fetch(self, subject: str, version: str) -> ResolvedSchema:
        subject_dir = self.base_path / subject
        if not subject_dir.is_dir():
            raise SchemaError(
                f"No schemas found for subject '{subject}'",
                context={"path": str(subject_dir)},
            )

        candidates = {
            self._version_of(path): path
            for path in subject_dir.iterdir()
            if path.suffix in _EXTENSION_FORMAT and self._version_of(path) is not None
        }
        if not candidates:
            raise SchemaError(
                f"No versioned schema files for subject '{subject}'",
                context={"path": str(subject_dir), "expected": "v<major> or <n>.<ext>"},
            )

        if version == "latest":
            resolved_version = max(candidates)
        else:
            resolved_version = int(re.sub(r"^v", "", version))
            if resolved_version not in candidates:
                raise SchemaError(
                    f"Schema version '{version}' not found for subject '{subject}'",
                    context={"available": sorted(candidates)},
                )

        path = candidates[resolved_version]
        raw = path.read_text(encoding="utf-8").strip()
        return ResolvedSchema(
            subject=subject,
            version=str(resolved_version),
            format=_EXTENSION_FORMAT[path.suffix],
            raw=raw,
        )

    @staticmethod
    def _version_of(path: Path) -> int | None:
        match = re.fullmatch(r"v?(\d+)", path.stem)
        return int(match.group(1)) if match else None


@schema_repository_registry.register("volume")
class VolumeSchemaRepository(FileSchemaRepository):
    """Unity Catalog volume — identical layout to the file repository."""


@schema_repository_registry.register("registry")
class SchemaRegistryRepository(SchemaRepository):
    """Confluent-compatible Schema Registry (REST).

    Options:
        url:  registry base url
        auth_header: optional Authorization header value (use ${secret:...})
    """

    def __init__(self, options: dict[str, str]) -> None:
        url = options.get("url")
        if not url:
            raise SchemaError("registry schema repository requires 'url' option")
        self.url = url.rstrip("/")
        self.auth_header = options.get("auth_header")

    def fetch(self, subject: str, version: str) -> ResolvedSchema:
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise SchemaError(
                "schema registry repository requires the 'requests' package "
                "(install dbx-rt-ingestion[http])",
                cause=exc,
            ) from exc

        headers = {"Authorization": self.auth_header} if self.auth_header else {}
        endpoint = f"{self.url}/subjects/{subject}/versions/{version}"
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code != 200:
            raise SchemaError(
                f"Schema registry returned {response.status_code} for "
                f"{subject}@{version}",
                context={"endpoint": endpoint},
            )
        body = response.json()
        schema_type = str(body.get("schemaType", "AVRO")).upper()
        fmt = {"AVRO": "avro", "JSON": "json_schema"}.get(schema_type)
        if fmt is None:
            raise SchemaError(
                f"Unsupported registry schema type '{schema_type}'",
                context={"subject": subject},
            )
        return ResolvedSchema(
            subject=subject,
            version=str(body["version"]),
            format=fmt,
            raw=str(body["schema"]),
        )


def build_schema_repository(repository_type: str, options: dict[str, str]) -> SchemaRepository:
    return schema_repository_registry.create(repository_type, options=options)


# JSON helper reused by the resolver
def json_schema_to_ddl_fields(document: str) -> list[tuple[str, str, bool]]:
    """Very small JSON-Schema (draft-7 subset) -> (name, spark type, nullable)."""

    type_map = {
        "string": "string",
        "integer": "bigint",
        "number": "double",
        "boolean": "boolean",
    }
    parsed = json.loads(document)
    required = set(parsed.get("required", []))
    fields: list[tuple[str, str, bool]] = []
    for name, prop in parsed.get("properties", {}).items():
        json_type = prop.get("type", "string")
        if isinstance(json_type, list):
            json_type = next((t for t in json_type if t != "null"), "string")
        spark_type = prop.get("sparkType") or type_map.get(json_type)
        if spark_type is None:
            raise SchemaError(
                f"Unsupported JSON schema type '{json_type}' for field '{name}' "
                "(add an explicit 'sparkType')"
            )
        fields.append((name, spark_type, name not in required))
    return fields
