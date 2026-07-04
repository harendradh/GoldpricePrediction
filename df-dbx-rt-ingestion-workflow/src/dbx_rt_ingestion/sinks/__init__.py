"""Sink implementations."""

from dbx_rt_ingestion.sinks.base import sink_registry

__all__ = ["sink_registry", "load_builtin_sinks"]


def load_builtin_sinks() -> None:
    """Import built-in sinks so their registry registrations execute."""

    from dbx_rt_ingestion.sinks import console_sink, delta_sink  # noqa: F401
