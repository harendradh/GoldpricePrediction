"""Schema mapping: model rules and loader mapping-file expansion."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dbx_rt_ingestion.config.loader import SpecLoader
from dbx_rt_ingestion.config.models import ColumnMappingSpec


def test_source_and_expr_are_mutually_exclusive() -> None:
    with pytest.raises(ValidationError):
        ColumnMappingSpec(target="a", source="x", expr="x + 1")


def test_source_defaults_to_target() -> None:
    mapping = ColumnMappingSpec(target="order_id")
    assert mapping.source is None
    assert mapping.expr is None


def test_mapping_file_expanded_into_topic(conf_dir: Path, app_spec_yaml: Path) -> None:
    mapping_file = conf_dir / "orders.mapping.yaml"
    mapping_file.write_text(
        """
columns:
  - target: order_id
    source: ord_id
  - target: amount_usd
    expr: "amt * fx_rate"
    type: decimal(18,2)
""",
        encoding="utf-8",
    )
    content = app_spec_yaml.read_text(encoding="utf-8").replace(
        "      parser:",
        f"      mapping_file: {mapping_file.as_posix()}\n      parser:",
    )
    app_spec_yaml.write_text(content, encoding="utf-8")

    spec = SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(app_spec_yaml)
    topic = spec.source.topics[0]
    assert [m.target for m in topic.mapping] == ["order_id", "amount_usd"]
    assert topic.mapping[1].expr == "amt * fx_rate"
