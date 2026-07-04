"""Spec loading: overlays, placeholders, validation errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from dbx_rt_ingestion.config.loader import SpecLoader, deep_merge
from dbx_rt_ingestion.core.exceptions import (
    ConfigurationError,
    SecretResolutionError,
    SpecValidationError,
)


def test_deep_merge_overlay_wins_and_nests() -> None:
    base = {"a": 1, "nested": {"x": 1, "y": 2}, "list": [1, 2]}
    overlay = {"nested": {"y": 99, "z": 3}, "list": [9]}
    merged = deep_merge(base, overlay)
    assert merged == {"a": 1, "nested": {"x": 1, "y": 99, "z": 3}, "list": [9]}
    assert base["nested"] == {"x": 1, "y": 2}  # base untouched


def test_load_valid_app_spec(conf_dir: Path, app_spec_yaml: Path) -> None:
    loader = SpecLoader(conf_dir=conf_dir, environment="dev")
    spec = loader.load_app_spec(app_spec_yaml)
    assert spec.name == "test-app"
    assert spec.source.topics[0].parser.type == "json"
    # dev overlay applied
    assert spec.observability.log_level == "DEBUG"


def test_cluster_environment_overlay(conf_dir: Path) -> None:
    dev = SpecLoader(conf_dir=conf_dir, environment="dev").load_cluster_spec("msk-test")
    prod = SpecLoader(conf_dir=conf_dir, environment="prod").load_cluster_spec("msk-test")
    assert dev.bootstrap_servers == "broker-1:9098"
    assert prod.bootstrap_servers == "broker-prod:9098"


def test_env_placeholder_resolution(
    conf_dir: Path, app_spec_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_CHECKPOINT", "/tmp/from-env")
    content = app_spec_yaml.read_text(encoding="utf-8").replace(
        "/tmp/checkpoints/test-app", "${env:TEST_CHECKPOINT}"
    )
    app_spec_yaml.write_text(content, encoding="utf-8")
    spec = SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(app_spec_yaml)
    assert spec.checkpoint_root == "/tmp/from-env"


def test_secret_placeholder_via_env_resolver(
    conf_dir: Path, app_spec_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MYSCOPE__TOKEN", "s3cret")
    content = app_spec_yaml.read_text(encoding="utf-8").replace(
        "main.test.events", "${secret:myscope/token}_table"
    )
    app_spec_yaml.write_text(content, encoding="utf-8")
    spec = SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(app_spec_yaml)
    assert spec.sink.table == "s3cret_table"


def test_unresolvable_secret_raises(conf_dir: Path, app_spec_yaml: Path) -> None:
    content = app_spec_yaml.read_text(encoding="utf-8").replace(
        "main.test.events", "${secret:nope/missing}"
    )
    app_spec_yaml.write_text(content, encoding="utf-8")
    with pytest.raises(SecretResolutionError):
        SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(app_spec_yaml)


def test_invalid_spec_reports_pydantic_errors(conf_dir: Path) -> None:
    bad = conf_dir / "bad.yaml"
    bad.write_text("name: x\n", encoding="utf-8")  # missing everything
    with pytest.raises(SpecValidationError) as exc:
        SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(bad)
    assert exc.value.context["errors"]


def test_missing_spec_file(conf_dir: Path) -> None:
    with pytest.raises(ConfigurationError):
        SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(
            conf_dir / "nope.yaml"
        )


def test_kafka_source_requires_cluster_and_topics(conf_dir: Path) -> None:
    bad = conf_dir / "bad2.yaml"
    bad.write_text(
        """
name: bad-app
domain: d
platform: p
source:
  type: kafka_msk
sink:
  type: delta
  table: t
checkpoint_root: /tmp/cp
""",
        encoding="utf-8",
    )
    with pytest.raises(SpecValidationError):
        SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(bad)
