"""Job scaffolder: functional spec -> complete, deployable pipeline.

Given one functional spec, generates every artifact a job needs (all Jinja2
templates under ``cli/templates/``):

    conf/jobs/<domain>/<job>.yaml                    runtime job config
    resources/schemas/<subject>/v1.ddl               schema (per topic)
    resources/schemas/<subject>/v1.mapping.yaml      schema mapping (per topic)
    resources/<domain>/<platform>_databricks.py      DAB entry artifact
    resources/<domain>/<job>.job.yml                 DAB job resource
    tests/jobs/test_<job>.py                         config validation test

The project-level ``databricks.yml`` picks up ``resources/**/*.job.yml``
automatically — after ``dfx job add`` the job is deployable with
``databricks bundle deploy``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined

from dbx_rt_ingestion.cli.functional_spec import FunctionalSpec, TopicDef
from dbx_rt_ingestion.core.exceptions import ConfigurationError


def _to_yaml(value: Any, indent: int = 0) -> str:
    """Jinja filter: dump a value as YAML, indented by ``indent`` spaces."""

    text = yaml.safe_dump(value, default_flow_style=False, sort_keys=False).rstrip()
    pad = " " * indent
    return "\n".join(pad + line for line in text.splitlines())


def _dump_models(models: list[Any]) -> list[dict[str, Any]]:
    """Jinja filter: pydantic models -> plain dicts (drop nulls and empties)."""

    dumped = []
    for model in models:
        data = model.model_dump(exclude_none=True)
        dumped.append({k: v for k, v in data.items() if v not in ({}, [], "")})
    return dumped


@dataclass
class ScaffoldResult:
    """Artifacts produced (or that would be produced) by one scaffold run."""

    written: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)


class JobScaffolder:
    """Renders all job artifacts from a functional spec."""

    def __init__(self, project_root: str | Path) -> None:
        self.root = Path(project_root)
        self.env = Environment(
            loader=PackageLoader("dbx_rt_ingestion.cli", "templates"),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            autoescape=False,
        )
        self.env.filters["to_yaml"] = _to_yaml
        self.env.filters["dump_models"] = _dump_models

    # ------------------------------------------------------------------ public
    def add_job(
        self, spec: FunctionalSpec, *, spec_source: str, force: bool = False
    ) -> ScaffoldResult:
        """Generate every artifact for one job; refuses overwrite unless force."""

        result = ScaffoldResult()
        context = self._context(spec, spec_source)

        for topic in spec.topics:
            self._emit(
                result,
                self.root / "resources" / "schemas" / topic.schema_subject / "v1.ddl",
                self._render("schema.ddl.j2", {**context, "topic": topic}),
                force,
            )
            if topic.mapping:
                self._emit(
                    result,
                    self.root
                    / "resources"
                    / "schemas"
                    / topic.schema_subject
                    / "v1.mapping.yaml",
                    self._render("mapping.yaml.j2", {**context, "topic": topic}),
                    force,
                )

        self._emit(
            result,
            self.root / "conf" / "jobs" / spec.job.domain / f"{spec.job_snake}.yaml",
            self._render("job_config.yaml.j2", context),
            force,
        )
        self._emit(
            result,
            self.root
            / "resources"
            / spec.job.domain
            / f"{spec.job.platform}_databricks.py",
            self._render("platform_databricks.py.j2", context),
            force,
        )
        self._emit(
            result,
            self.root / "resources" / spec.job.domain / f"{spec.job_snake}.job.yml",
            self._render("job_resource.yml.j2", context),
            force,
        )
        self._emit(
            result,
            self.root / "tests" / "jobs" / f"test_{spec.job_snake}.py",
            self._render("test_job.py.j2", context),
            force,
        )
        return result

    # ---------------------------------------------------------------- internal
    def _context(self, spec: FunctionalSpec, spec_source: str) -> dict[str, Any]:
        return {
            "spec": spec,
            "job": spec.job,
            "job_snake": spec.job_snake,
            "source": spec.source,
            "topics": spec.topics,
            "sink": spec.sink,
            "trigger": spec.trigger,
            "tags": spec.tags,
            "spec_source": spec_source.replace("\\", "/"),
            "mapping_file_for": self._mapping_file_for,
        }

    @staticmethod
    def _mapping_file_for(topic: TopicDef) -> str:
        return f"resources/schemas/{topic.schema_subject}/v1.mapping.yaml"

    def _render(self, template: str, context: dict[str, Any]) -> str:
        return self.env.get_template(template).render(**context)

    def _emit(
        self, result: ScaffoldResult, path: Path, content: str, force: bool
    ) -> None:
        if path.exists() and not force:
            existing = path.read_text(encoding="utf-8")
            if existing == content:
                result.skipped.append(path)
                return
            raise ConfigurationError(
                f"Refusing to overwrite existing file (use --force): {path}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        result.written.append(path)
