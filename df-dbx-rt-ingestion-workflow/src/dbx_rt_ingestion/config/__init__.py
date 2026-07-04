"""Specification-driven configuration: models, loading, secrets, validation."""

from dbx_rt_ingestion.config.loader import SpecLoader
from dbx_rt_ingestion.config.models import AppSpec

__all__ = ["AppSpec", "SpecLoader"]
