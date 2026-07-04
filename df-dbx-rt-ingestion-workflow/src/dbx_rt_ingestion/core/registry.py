"""Generic plug-in registry.

All extension points (sources, parsers, sinks, auth providers, schema
repositories, metric publishers) use this registry so new implementations are
added by registration, never by modifying framework code (Open/Closed).

Usage::

    parser_registry: Registry[Parser] = Registry("parser")

    @parser_registry.register("json")
    class JsonParser(BaseParser): ...

    parser = parser_registry.create("json", spec=parser_spec)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar

from dbx_rt_ingestion.core.exceptions import ConfigurationError

T = TypeVar("T")


class Registry(Generic[T]):
    """Name -> class registry for a single extension point."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._entries: dict[str, type[T]] = {}

    @property
    def kind(self) -> str:
        return self._kind

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        """Class decorator registering ``cls`` under ``name`` (case-insensitive)."""

        key = name.strip().lower()

        def decorator(cls: type[T]) -> type[T]:
            if key in self._entries and self._entries[key] is not cls:
                raise ConfigurationError(
                    f"Duplicate {self._kind} registration for '{key}'",
                    context={"existing": self._entries[key].__name__, "new": cls.__name__},
                )
            self._entries[key] = cls
            return cls

        return decorator

    def get(self, name: str) -> type[T]:
        key = name.strip().lower()
        if key not in self._entries:
            raise ConfigurationError(
                f"Unknown {self._kind} '{name}'",
                context={"available": sorted(self._entries)},
            )
        return self._entries[key]

    def create(self, name: str, **kwargs: Any) -> T:
        return self.get(name)(**kwargs)

    def names(self) -> list[str]:
        return sorted(self._entries)

    def __contains__(self, name: str) -> bool:
        return name.strip().lower() in self._entries
