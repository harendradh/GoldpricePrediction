"""Configuration loading: file -> merged, resolved, validated models.

Format-agnostic: job configs, cluster definitions, environment overlays, and
mapping files may be YAML (default), JSON, or TOML — chosen by extension.
YAML remains the recommended format because Databricks Asset Bundles and the
generated artifacts are YAML; the models in ``config/models.py`` are the real
contract, the file format is just serialization.

Resolution order (later wins):
1. Base job config            conf/jobs/<domain>/<job>.yaml
2. Environment overlay        conf/environments/<env>.yaml  (``overrides`` block)
3. Mapping-file expansion     topic.mapping_file -> topic.mapping
4. Placeholder resolution     ${env:NAME}, ${secret:scope/key}

Cluster definitions live in conf/clusters/<name>.<ext> and are resolved by
name from ``source.cluster``.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from dbx_rt_ingestion.config.models import AppSpec, ClusterSpec
from dbx_rt_ingestion.config.secrets import ChainSecretResolver
from dbx_rt_ingestion.core.exceptions import ConfigurationError, SpecValidationError

_PLACEHOLDER = re.compile(r"\$\{(secret|env):([^}]+)\}")
_CONFIG_EXTENSIONS = (".yaml", ".yml", ".json", ".toml")


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` onto ``base`` (overlay wins; lists replace)."""

    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def read_config_file(path: Path) -> dict[str, Any]:
    """Parse a config file by extension (yaml/yml/json/toml)."""

    if not path.exists():
        raise ConfigurationError(f"Config file not found: {path}")
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        content = yaml.safe_load(text)
    elif suffix == ".json":
        content = json.loads(text)
    elif suffix == ".toml":
        import tomllib

        content = tomllib.loads(text)
    else:
        raise ConfigurationError(
            f"Unsupported config format '{suffix}' for {path}",
            context={"supported": list(_CONFIG_EXTENSIONS)},
        )
    if not isinstance(content, dict):
        raise ConfigurationError(f"Config file is not a mapping: {path}")
    return content


class SpecLoader:
    """Loads and resolves job and cluster configurations."""

    def __init__(
        self,
        conf_dir: str | Path,
        environment: str,
        secret_resolver: ChainSecretResolver | None = None,
    ) -> None:
        self.conf_dir = Path(conf_dir)
        self.environment = environment
        self._secrets = secret_resolver or ChainSecretResolver()

    # ------------------------------------------------------------------ public
    def load_app_spec(self, spec_path: str | Path) -> AppSpec:
        """Load, overlay, expand mappings, resolve, and validate one job config."""

        raw = read_config_file(Path(spec_path))
        raw = self._apply_environment_overlay(raw)
        raw = self._expand_mapping_files(raw)
        raw = self._resolve_placeholders(raw)
        try:
            return AppSpec.model_validate(raw)
        except ValidationError as exc:
            raise SpecValidationError(
                f"Job config '{spec_path}' is invalid",
                context={"errors": exc.errors(include_url=False)},
                cause=exc,
            ) from exc

    def load_cluster_spec(self, cluster_name: str) -> ClusterSpec:
        """Load a named cluster definition with env overlay + secret resolution."""

        raw = read_config_file(self._find_config(self.conf_dir / "clusters", cluster_name))
        env_block = raw.pop("environments", {}) or {}
        if self.environment in env_block:
            raw = deep_merge(raw, env_block[self.environment])
        raw = self._resolve_placeholders(raw)
        try:
            return ClusterSpec.model_validate(raw)
        except ValidationError as exc:
            raise SpecValidationError(
                f"Cluster config '{cluster_name}' is invalid",
                context={"errors": exc.errors(include_url=False)},
                cause=exc,
            ) from exc

    # ----------------------------------------------------------------- internal
    @staticmethod
    def _find_config(directory: Path, stem: str) -> Path:
        for extension in _CONFIG_EXTENSIONS:
            candidate = directory / f"{stem}{extension}"
            if candidate.exists():
                return candidate
        raise ConfigurationError(
            f"No config file '{stem}.(yaml|yml|json|toml)' in {directory}"
        )

    def _apply_environment_overlay(self, raw: dict[str, Any]) -> dict[str, Any]:
        env_dir = self.conf_dir / "environments"
        try:
            env_file = self._find_config(env_dir, self.environment)
        except ConfigurationError:
            return raw
        overrides = read_config_file(env_file).get("overrides", {}) or {}
        return deep_merge(raw, overrides)

    def _expand_mapping_files(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Inline each topic's ``mapping_file`` into its ``mapping`` list."""

        topics = (raw.get("source") or {}).get("topics") or []
        for topic in topics:
            if not isinstance(topic, dict) or not topic.get("mapping_file"):
                continue
            mapping_path = self._resolve_relative(str(topic["mapping_file"]))
            document = read_config_file(mapping_path)
            columns = document.get("columns")
            if not isinstance(columns, list):
                raise ConfigurationError(
                    f"Mapping file '{mapping_path}' must have a top-level 'columns:' list"
                )
            topic["mapping"] = columns
        return raw

    def _resolve_relative(self, reference: str) -> Path:
        """Resolve a file reference: absolute, project-root-, or conf-relative."""

        path = Path(reference)
        if path.is_absolute():
            return path
        for base in (self.conf_dir.parent, self.conf_dir, Path.cwd()):
            candidate = base / path
            if candidate.exists():
                return candidate
        raise ConfigurationError(
            f"Referenced file not found: {reference}",
            context={"searched": [str(self.conf_dir.parent), str(self.conf_dir), "cwd"]},
        )

    def _resolve_placeholders(self, node: Any) -> Any:
        if isinstance(node, dict):
            return {k: self._resolve_placeholders(v) for k, v in node.items()}
        if isinstance(node, list):
            return [self._resolve_placeholders(item) for item in node]
        if isinstance(node, str):
            return _PLACEHOLDER.sub(self._substitute, node)
        return node

    def _substitute(self, match: re.Match[str]) -> str:
        kind, ref = match.group(1), match.group(2).strip()
        if kind == "env":
            value = os.environ.get(ref)
            if value is None:
                raise ConfigurationError(f"Environment variable '{ref}' is not set")
            return value
        scope, _, key = ref.partition("/")
        if not scope or not key:
            raise ConfigurationError(
                f"Malformed secret reference '${{secret:{ref}}}' (expected scope/key)"
            )
        return self._secrets.resolve(scope, key)
