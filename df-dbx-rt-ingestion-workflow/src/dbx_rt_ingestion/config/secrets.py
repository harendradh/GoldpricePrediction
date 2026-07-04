"""Secrets management integration.

Specs never contain literal secrets. Values reference secrets with
``${secret:scope/key}`` placeholders which are resolved at startup through a
chain of resolvers: Databricks secret scopes first (on Databricks), then
environment variables (local/dev), so the same spec runs everywhere.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from dbx_rt_ingestion.core.exceptions import SecretResolutionError


class SecretResolver(ABC):
    """Resolves a secret reference to its value."""

    @abstractmethod
    def resolve(self, scope: str, key: str) -> str | None:
        """Return the secret value, or None if this resolver cannot supply it."""


class DatabricksSecretResolver(SecretResolver):
    """Resolves via ``dbutils.secrets`` when running on Databricks."""

    def __init__(self) -> None:
        self._dbutils = self._locate_dbutils()

    @staticmethod
    def _locate_dbutils() -> object | None:
        try:  # Databricks notebooks / jobs expose dbutils via IPython
            from IPython import get_ipython  # type: ignore[import-not-found]

            shell = get_ipython()
            if shell is not None:
                return shell.user_ns.get("dbutils")
        except ImportError:
            pass
        return None

    @property
    def available(self) -> bool:
        return self._dbutils is not None

    def resolve(self, scope: str, key: str) -> str | None:
        if self._dbutils is None:
            return None
        try:
            return str(self._dbutils.secrets.get(scope=scope, key=key))  # type: ignore[attr-defined]
        except Exception:
            return None


class EnvSecretResolver(SecretResolver):
    """Resolves from environment variables named ``<SCOPE>__<KEY>`` (upper-cased,

    non-alphanumerics replaced with underscores). Intended for local dev and CI.
    """

    def resolve(self, scope: str, key: str) -> str | None:
        env_name = f"{scope}__{key}".upper().replace("-", "_").replace("/", "_")
        return os.environ.get(env_name)


class ChainSecretResolver(SecretResolver):
    """Tries each resolver in order; raises if none can resolve."""

    def __init__(self, resolvers: list[SecretResolver] | None = None) -> None:
        self._resolvers = resolvers or [DatabricksSecretResolver(), EnvSecretResolver()]

    def resolve(self, scope: str, key: str) -> str:
        for resolver in self._resolvers:
            value = resolver.resolve(scope, key)
            if value is not None:
                return value
        raise SecretResolutionError(
            f"Secret '{scope}/{key}' could not be resolved",
            context={"resolvers": [type(r).__name__ for r in self._resolvers]},
        )
