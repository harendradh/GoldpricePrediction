"""Startup validation: registry references and semantic checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from dbx_rt_ingestion.config.loader import SpecLoader
from dbx_rt_ingestion.config.validation import validate_app_spec
from dbx_rt_ingestion.core.exceptions import SpecValidationError


def test_valid_spec_passes(conf_dir: Path, app_spec_yaml: Path) -> None:
    spec = SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(app_spec_yaml)
    validate_app_spec(spec)  # must not raise


def test_unknown_parser_is_reported(conf_dir: Path, app_spec_yaml: Path) -> None:
    content = app_spec_yaml.read_text(encoding="utf-8").replace(
        "type: json", "type: not_a_parser"
    )
    app_spec_yaml.write_text(content, encoding="utf-8")
    spec = SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(app_spec_yaml)
    with pytest.raises(SpecValidationError) as exc:
        validate_app_spec(spec)
    assert any("not_a_parser" in p for p in exc.value.context["problems"])


def test_platform_parser_is_registered(conf_dir: Path, app_spec_yaml: Path) -> None:
    content = app_spec_yaml.read_text(encoding="utf-8").replace(
        "type: json", "type: platform_a.account"
    )
    app_spec_yaml.write_text(content, encoding="utf-8")
    spec = SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(app_spec_yaml)
    validate_app_spec(spec)  # platform_a.account ships with the framework
