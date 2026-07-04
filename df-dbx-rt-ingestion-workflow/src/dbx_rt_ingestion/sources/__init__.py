"""Streaming source implementations."""

from dbx_rt_ingestion.sources.base import source_registry

__all__ = ["source_registry", "load_builtin_sources"]


def load_builtin_sources() -> None:
    """Import built-in sources so their registry registrations execute."""

    from dbx_rt_ingestion.sources import autoloader, kafka  # noqa: F401
