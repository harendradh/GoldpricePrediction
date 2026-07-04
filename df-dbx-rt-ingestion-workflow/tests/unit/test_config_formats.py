"""Format-agnostic config loading: YAML, JSON, TOML."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from dbx_rt_ingestion.config.loader import SpecLoader, read_config_file
from dbx_rt_ingestion.core.exceptions import ConfigurationError


def test_json_job_config_loads(conf_dir: Path, app_spec_yaml: Path) -> None:
    data = yaml.safe_load(app_spec_yaml.read_text(encoding="utf-8"))
    json_spec = conf_dir / "app.json"
    json_spec.write_text(json.dumps(data), encoding="utf-8")

    spec = SpecLoader(conf_dir=conf_dir, environment="dev").load_app_spec(json_spec)
    assert spec.name == "test-app"


def test_toml_cluster_loads(conf_dir: Path) -> None:
    (conf_dir / "clusters" / "toml-cluster.toml").write_text(
        """
name = "toml-cluster"
provider = "generic"
bootstrap_servers = "broker:9092"

[auth]
type = "none"
""",
        encoding="utf-8",
    )
    cluster = SpecLoader(conf_dir=conf_dir, environment="dev").load_cluster_spec(
        "toml-cluster"
    )
    assert cluster.bootstrap_servers == "broker:9092"


def test_unsupported_extension_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "config.ini"
    bad.write_text("[x]\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        read_config_file(bad)
