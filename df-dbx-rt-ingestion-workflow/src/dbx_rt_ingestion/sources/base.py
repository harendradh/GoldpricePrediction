"""Source registry and shared base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.core.interfaces import StreamingSource
from dbx_rt_ingestion.core.registry import Registry

if TYPE_CHECKING:  # pragma: no cover
    from dbx_rt_ingestion.config.models import ClusterSpec, SourceSpec, TopicSpec

source_registry: Registry[StreamingSource] = Registry("streaming source")


class BaseStreamingSource(StreamingSource):
    """Holds the resolved specs every source needs."""

    def __init__(
        self,
        source_spec: SourceSpec,
        cluster_spec: ClusterSpec | None = None,
        topic_spec: TopicSpec | None = None,
    ) -> None:
        self.source_spec = source_spec
        self.cluster_spec = cluster_spec
        self.topic_spec = topic_spec
