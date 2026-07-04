"""Framework contracts (abstract base classes).

These interfaces are the stable extension points of the framework. All
concrete implementations register themselves in a `Registry` and are resolved
from the application specification at runtime — never hard-coded.

PySpark types are imported only for type checking so the framework can be
imported (and unit tested) without a Spark runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame
    from pyspark.sql.streaming import StreamingQuery

    from dbx_rt_ingestion.core.context import PipelineContext
    from dbx_rt_ingestion.schema.resolver import ResolvedSchema


class StreamingSource(ABC):
    """Produces a streaming DataFrame from an external system (Kafka, files)."""

    @abstractmethod
    def read(self, ctx: PipelineContext) -> DataFrame:
        """Return an unbounded (readStream) DataFrame."""


class Parser(ABC):
    """Transforms raw source records into a typed, business-ready DataFrame.

    Contract:
    - MUST preserve framework metadata columns (``_dfx_*``).
    - MUST NOT throw on malformed records; instead populate ``_dfx_error`` so
      the pipeline can route them to the Dead Letter Queue.
    - MUST be a pure DataFrame -> DataFrame transformation (no actions).
    """

    @abstractmethod
    def parse(self, df: DataFrame, ctx: PipelineContext) -> DataFrame:
        """Return the parsed DataFrame."""


class Sink(ABC):
    """Writes a streaming DataFrame to a target system."""

    @abstractmethod
    def write(self, df: DataFrame, ctx: PipelineContext) -> StreamingQuery:
        """Start and return the streaming query."""


class AuthProvider(ABC):
    """Produces connection security options for a source.

    For Kafka sources the returned dict uses fully-qualified option names
    (already prefixed with ``kafka.``), e.g. ``kafka.security.protocol``.
    """

    @abstractmethod
    def kafka_options(self) -> dict[str, str]:
        """Return security-related reader options."""


class SchemaRepository(ABC):
    """Loads schema documents from a centralized location."""

    @abstractmethod
    def fetch(self, subject: str, version: str) -> ResolvedSchema:
        """Return the schema for ``subject`` at ``version`` ('latest' allowed)."""


class MetricsPublisher(ABC):
    """Publishes operational metric events to a monitoring platform."""

    @abstractmethod
    def publish(self, event: dict[str, Any]) -> None:
        """Publish one metric event. Must never raise into the caller."""

    def close(self) -> None:  # noqa: B027 - optional hook
        """Release resources (optional)."""
