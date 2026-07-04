"""dfx CLI: functional spec parsing and end-to-end job scaffolding."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from dbx_rt_ingestion.cli.functional_spec import parse_functional_spec
from dbx_rt_ingestion.cli.main import cli
from dbx_rt_ingestion.core.exceptions import SpecValidationError

_FUNCTIONAL_SPEC = """---
job:
  name: demo-orders
  domain: demo
  platform: platform_x
  description: Demo orders ingestion.
source:
  type: kafka_msk
  cluster: msk-test
topics:
  - name: demo.orders.v1
    format: json
    schema_subject: platform_x.orders
    fields:
      - { name: ord_id, type: string, nullable: false }
      - { name: amt, type: "decimal(18,4)" }
    mapping:
      - { target: order_id, source: ord_id }
      - { target: amount_cents, expr: "amt * 100", type: bigint }
    quality:
      - { name: ord_id_present, type: not_null, column: ord_id }
sink:
  catalog: main
  schema: demo
  table: orders
  mode: merge
  merge_keys: [order_id]
---

# demo-orders

Prose section.
"""


@pytest.fixture()
def project(tmp_path: Path, conf_dir: Path) -> Path:
    """A minimal project root reusing the conf fixture's clusters/environments."""

    import shutil

    root = tmp_path / "project"
    (root / "conf").mkdir(parents=True)
    shutil.copytree(conf_dir / "clusters", root / "conf" / "clusters")
    shutil.copytree(conf_dir / "environments", root / "conf" / "environments")
    spec_file = root / "specs" / "demo" / "demo_orders.md"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text(_FUNCTIONAL_SPEC, encoding="utf-8")
    return root


def test_parse_functional_spec(project: Path) -> None:
    spec = parse_functional_spec(project / "specs" / "demo" / "demo_orders.md")
    assert spec.job.name == "demo-orders"
    assert spec.job_snake == "demo_orders"
    assert spec.topics[0].mapping[1].expr == "amt * 100"


def test_missing_front_matter_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("# just prose\n", encoding="utf-8")
    with pytest.raises(SpecValidationError):
        parse_functional_spec(bad)


def test_job_add_generates_all_artifacts(project: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "job", "add",
            "--spec", str(project / "specs" / "demo" / "demo_orders.md"),
            "--root", str(project),
        ],
    )
    assert result.exit_code == 0, result.output

    expected = [
        project / "conf" / "jobs" / "demo" / "demo_orders.yaml",
        project / "resources" / "schemas" / "platform_x.orders" / "v1.ddl",
        project / "resources" / "schemas" / "platform_x.orders" / "v1.mapping.yaml",
        project / "resources" / "demo" / "platform_x_databricks.py",
        project / "resources" / "demo" / "demo_orders.job.yml",
        project / "tests" / "jobs" / "test_demo_orders.py",
    ]
    for path in expected:
        assert path.exists(), f"missing artifact: {path}"

    assert "VALID: demo-orders" in result.output

    ddl = (expected[1]).read_text(encoding="utf-8")
    assert "ord_id string" in ddl

    generated_config = expected[0].read_text(encoding="utf-8")
    assert "mapping_file: resources/schemas/platform_x.orders/v1.mapping.yaml" in generated_config
    assert "merge_keys" in generated_config


def test_job_add_refuses_overwrite_without_force(project: Path) -> None:
    runner = CliRunner()
    args = [
        "job", "add",
        "--spec", str(project / "specs" / "demo" / "demo_orders.md"),
        "--root", str(project),
    ]
    assert runner.invoke(cli, args).exit_code == 0

    # identical content -> idempotent skip
    rerun = runner.invoke(cli, args)
    assert rerun.exit_code == 0
    assert "current" in rerun.output

    # changed spec -> refuse without --force
    spec_file = project / "specs" / "demo" / "demo_orders.md"
    spec_file.write_text(
        spec_file.read_text(encoding="utf-8").replace("Demo orders", "Changed"),
        encoding="utf-8",
    )
    blocked = runner.invoke(cli, args)
    assert blocked.exit_code != 0
    assert "--force" in blocked.output

    forced = runner.invoke(cli, [*args, "--force"])
    assert forced.exit_code == 0, forced.output


def test_generated_config_validates_with_mapping(project: Path) -> None:
    from dbx_rt_ingestion.config.loader import SpecLoader
    from dbx_rt_ingestion.config.validation import validate_app_spec

    runner = CliRunner()
    assert (
        runner.invoke(
            cli,
            [
                "job", "add",
                "--spec", str(project / "specs" / "demo" / "demo_orders.md"),
                "--root", str(project),
                "--skip-validate",
            ],
        ).exit_code
        == 0
    )
    loader = SpecLoader(conf_dir=project / "conf", environment="dev")
    spec = loader.load_app_spec(project / "conf" / "jobs" / "demo" / "demo_orders.yaml")
    validate_app_spec(spec)
    assert [m.target for m in spec.source.topics[0].mapping] == [
        "order_id",
        "amount_cents",
    ]
