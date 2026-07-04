"""dfx — developer CLI for df-dbx-rt-ingestion-workflow (Click).

Commands:
    dfx spec init      scaffold a new functional spec from the template
    dfx job add        functional spec -> complete deployable pipeline
    dfx job validate   validate a generated job config for an environment
    dfx job list       list jobs known to the project
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from dbx_rt_ingestion import __version__
from dbx_rt_ingestion.cli.functional_spec import parse_functional_spec
from dbx_rt_ingestion.cli.scaffold import JobScaffolder
from dbx_rt_ingestion.core.exceptions import FrameworkError


@click.group()
@click.version_option(version=__version__, prog_name="dfx")
def cli() -> None:
    """df-dbx-rt-ingestion-workflow developer CLI."""


# ------------------------------------------------------------------------- spec
@cli.group()
def spec() -> None:
    """Functional specification commands."""


@spec.command("init")
@click.option("--domain", required=True, help="Business domain, e.g. gbs_auth.")
@click.option("--name", "job_name", required=True, help="Job name (kebab-case).")
@click.option("--root", default=".", type=click.Path(file_okay=False), show_default=True)
def spec_init(domain: str, job_name: str, root: str) -> None:
    """Create a new functional spec from the template under specs/<domain>/."""

    template = Path(root) / "specs" / "_template.md"
    if not template.exists():
        raise click.ClickException(f"Spec template not found: {template}")
    target = Path(root) / "specs" / domain / f"{job_name.replace('-', '_')}.md"
    if target.exists():
        raise click.ClickException(f"Spec already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    content = template.read_text(encoding="utf-8").replace("<JOB_NAME>", job_name)
    target.write_text(content.replace("<DOMAIN>", domain), encoding="utf-8")
    click.echo(f"Created {target}")
    click.echo("Fill in the front matter, then run: dfx job add --spec " + str(target))


# -------------------------------------------------------------------------- job
@cli.group()
def job() -> None:
    """Job lifecycle commands."""


@job.command("add")
@click.option(
    "--spec",
    "spec_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the functional spec markdown file.",
)
@click.option("--root", default=".", type=click.Path(file_okay=False), show_default=True)
@click.option("--force", is_flag=True, help="Overwrite previously generated artifacts.")
@click.option("--env", default="dev", show_default=True, help="Environment to validate against.")
@click.option("--skip-validate", is_flag=True, help="Skip post-generation validation.")
def job_add(spec_path: str, root: str, force: bool, env: str, skip_validate: bool) -> None:
    """Generate the end-to-end pipeline for one functional spec."""

    try:
        functional = parse_functional_spec(spec_path)
        rel_source = _relativize(spec_path, root)
        result = JobScaffolder(root).add_job(
            functional, spec_source=rel_source, force=force
        )
    except FrameworkError as exc:
        raise click.ClickException(str(exc)) from exc

    for path in result.written:
        click.echo(f"  wrote    {_relativize(path, root)}")
    for path in result.skipped:
        click.echo(f"  current  {_relativize(path, root)}")

    if not skip_validate:
        config = (
            Path(root) / "conf" / "jobs" / functional.job.domain
            / f"{functional.job_snake}.yaml"
        )
        _validate(config, env, Path(root))

    click.secho(f"Job '{functional.job.name}' is ready.", fg="green")
    click.echo("Deploy with: databricks bundle deploy -t " + env)


@job.command("validate")
@click.option(
    "--config",
    "config_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the generated job config (conf/jobs/...).",
)
@click.option("--env", default="dev", show_default=True)
@click.option("--root", default=".", type=click.Path(file_okay=False), show_default=True)
def job_validate(config_path: str, env: str, root: str) -> None:
    """Validate a job config against all registries for an environment."""

    _validate(Path(config_path), env, Path(root))


@job.command("list")
@click.option("--root", default=".", type=click.Path(file_okay=False), show_default=True)
def job_list(root: str) -> None:
    """List job configs in the project."""

    jobs_dir = Path(root) / "conf" / "jobs"
    configs = sorted(jobs_dir.rglob("*.y*ml")) if jobs_dir.exists() else []
    if not configs:
        click.echo("No jobs found under conf/jobs/.")
        return
    for config in configs:
        click.echo(f"  {_relativize(config, root)}")


# ---------------------------------------------------------------------- helpers
def _validate(config: Path, env: str, root: Path) -> None:
    from dbx_rt_ingestion.config.loader import SpecLoader
    from dbx_rt_ingestion.config.validation import validate_app_spec

    try:
        loader = SpecLoader(conf_dir=root / "conf", environment=env)
        app_spec = loader.load_app_spec(config)
        validate_app_spec(app_spec)
    except FrameworkError as exc:
        click.secho(f"INVALID: {exc}", fg="red", err=True)
        sys.exit(1)
    click.secho(f"VALID: {app_spec.name} ({env})", fg="green")

    if app_spec.source.cluster:
        try:
            loader.load_cluster_spec(app_spec.source.cluster)
        except FrameworkError as exc:
            click.secho(
                f"warning: cluster '{app_spec.source.cluster}' not resolvable: {exc}",
                fg="yellow",
            )


def _relativize(path: str | Path, root: str | Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    cli()
