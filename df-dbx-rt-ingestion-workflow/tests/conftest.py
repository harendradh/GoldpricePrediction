"""Shared test fixtures. Spark-dependent tests use pytest.importorskip."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running tests without an editable install.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture()
def conf_dir(tmp_path: Path) -> Path:
    """Minimal conf tree with one cluster, one environment, one schema."""

    (tmp_path / "clusters").mkdir()
    (tmp_path / "environments").mkdir()
    schemas = tmp_path / "schemas" / "platform_a.events"
    schemas.mkdir(parents=True)

    (tmp_path / "clusters" / "msk-test.yaml").write_text(
        """
name: msk-test
provider: msk
bootstrap_servers: "broker-1:9098"
auth:
  type: msk_iam
environments:
  prod:
    bootstrap_servers: "broker-prod:9098"
""",
        encoding="utf-8",
    )
    (tmp_path / "environments" / "dev.yaml").write_text(
        """
overrides:
  observability:
    log_level: DEBUG
""",
        encoding="utf-8",
    )
    (schemas / "v1.ddl").write_text("event_id string, amount double", encoding="utf-8")
    (schemas / "v2.ddl").write_text(
        "event_id string, amount double, currency string", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def app_spec_yaml(conf_dir: Path) -> Path:
    """A valid minimal application spec referencing the test conf tree."""

    spec = conf_dir / "app.yaml"
    spec.write_text(
        f"""
name: test-app
domain: gbs-auth
platform: platform_a
source:
  type: kafka_msk
  cluster: msk-test
  topics:
    - name: test.topic.v1
      schema:
        subject: platform_a.events
        version: latest
      parser:
        type: json
sink:
  type: delta
  table: main.test.events
checkpoint_root: /tmp/checkpoints/test-app
schema_management:
  repository: file
  options:
    base_path: {(conf_dir / 'schemas').as_posix()}
""",
        encoding="utf-8",
    )
    return spec
