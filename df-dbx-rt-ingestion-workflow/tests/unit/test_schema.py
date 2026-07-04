"""Schema repository and evolution checks (Spark-free where possible)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dbx_rt_ingestion.core.exceptions import SchemaError
from dbx_rt_ingestion.schema.repository import FileSchemaRepository


def _repo(conf_dir: Path) -> FileSchemaRepository:
    return FileSchemaRepository({"base_path": str(conf_dir / "schemas")})


def test_latest_resolves_highest_version(conf_dir: Path) -> None:
    resolved = _repo(conf_dir).fetch("platform_a.events", "latest")
    assert resolved.version == "2"
    assert "currency" in resolved.raw


def test_pinned_version(conf_dir: Path) -> None:
    resolved = _repo(conf_dir).fetch("platform_a.events", "v1")
    assert resolved.version == "1"
    assert resolved.format == "ddl"


def test_unknown_subject(conf_dir: Path) -> None:
    with pytest.raises(SchemaError):
        _repo(conf_dir).fetch("does.not.exist", "latest")


def test_unknown_version(conf_dir: Path) -> None:
    with pytest.raises(SchemaError) as exc:
        _repo(conf_dir).fetch("platform_a.events", "v9")
    assert exc.value.context["available"] == [1, 2]


def _struct(*fields: tuple[str, object, bool]):  # noqa: ANN202
    from pyspark.sql.types import StructField, StructType

    return StructType([StructField(n, t, nullable) for n, t, nullable in fields])


def test_evolution_backward_compatible() -> None:
    pytest.importorskip("pyspark")
    from pyspark.sql.types import DoubleType, StringType

    from dbx_rt_ingestion.schema.evolution import check_compatibility

    old = _struct(("id", StringType(), True), ("amount", DoubleType(), True))
    new = _struct(
        ("id", StringType(), True),
        ("amount", DoubleType(), True),
        ("currency", StringType(), True),
    )
    check_compatibility(old, new, "backward", subject="t")  # must not raise


def test_evolution_removed_field_violates_backward() -> None:
    pytest.importorskip("pyspark")
    from pyspark.sql.types import DoubleType, StringType

    from dbx_rt_ingestion.core.exceptions import SchemaCompatibilityError
    from dbx_rt_ingestion.schema.evolution import check_compatibility

    old = _struct(("id", StringType(), True), ("amount", DoubleType(), True))
    new = _struct(("id", StringType(), True))
    with pytest.raises(SchemaCompatibilityError):
        check_compatibility(old, new, "backward", subject="t")


def test_evolution_new_required_field_violates_backward() -> None:
    pytest.importorskip("pyspark")
    from pyspark.sql.types import StringType

    from dbx_rt_ingestion.core.exceptions import SchemaCompatibilityError
    from dbx_rt_ingestion.schema.evolution import check_compatibility

    old = _struct(("id", StringType(), True))
    new = _struct(("id", StringType(), True), ("mandatory", StringType(), False))
    with pytest.raises(SchemaCompatibilityError):
        check_compatibility(old, new, "backward", subject="t")
