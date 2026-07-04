"""Core framework primitives: contracts, registries, errors, logging, context."""

from dbx_rt_ingestion.core.exceptions import FrameworkError
from dbx_rt_ingestion.core.registry import Registry

__all__ = ["FrameworkError", "Registry"]
