"""Kafka streaming sources (AWS MSK, Cloudera, generic).

Option precedence (later wins):
1. Provider defaults (per source class)
2. Auth provider options
3. Cluster spec options
4. Source spec options
5. Topic spec options

One source instance reads ONE topic — parser and schema resolution are
per-topic, so each topic runs as its own pipeline with an isolated checkpoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dbx_rt_ingestion.auth.providers import build_auth_provider
from dbx_rt_ingestion.core.exceptions import SourceError
from dbx_rt_ingestion.sources.base import BaseStreamingSource, source_registry

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame

    from dbx_rt_ingestion.core.context import PipelineContext


class KafkaSource(BaseStreamingSource):
    """Generic Kafka source; MSK/Cloudera subclasses adjust defaults."""

    #: sensible enterprise defaults; overridable at any level
    provider_defaults: dict[str, str] = {
        "startingOffsets": "earliest",
        "failOnDataLoss": "false",
        "maxOffsetsPerTrigger": "1000000",
    }

    def reader_options(self) -> dict[str, str]:
        """Assemble the final Kafka reader options with documented precedence."""

        if self.cluster_spec is None or self.topic_spec is None:
            raise SourceError(
                "Kafka source requires cluster and topic specs",
                context={"source_type": self.source_spec.type},
            )
        auth = build_auth_provider(self.cluster_spec.auth)
        options: dict[str, str] = {}
        options.update(self.provider_defaults)
        options.update(auth.kafka_options())
        options.update(self.cluster_spec.options)
        options.update(self.source_spec.options)
        options.update(self.topic_spec.options)
        options["kafka.bootstrap.servers"] = self.cluster_spec.bootstrap_servers
        options["subscribe"] = self.topic_spec.name
        return options

    def read(self, ctx: PipelineContext) -> DataFrame:
        from pyspark.sql import functions as F

        options = self.reader_options()
        try:
            df = ctx.spark.readStream.format("kafka").options(**options).load()
        except Exception as exc:  # pragma: no cover - spark runtime failure
            raise SourceError(
                f"Failed to open Kafka stream for topic '{options.get('subscribe')}'",
                context={"cluster": self.cluster_spec.name if self.cluster_spec else None},
                cause=exc,
            ) from exc

        # Standardized framework metadata columns, preserved through parsing.
        return df.select(
            F.col("key").alias("_dfx_key"),
            F.col("value").alias("_dfx_value"),
            F.col("topic").alias("_dfx_topic"),
            F.col("partition").alias("_dfx_partition"),
            F.col("offset").alias("_dfx_offset"),
            F.col("timestamp").alias("_dfx_kafka_timestamp"),
            F.current_timestamp().alias("_dfx_ingest_timestamp"),
            F.lit(None).cast("string").alias("_dfx_error"),
        )


@source_registry.register("kafka_msk")
class MskKafkaSource(KafkaSource):
    """AWS MSK. Typical auth: msk_iam, mtls, or sasl_ssl (SCRAM)."""

    provider_defaults = {
        **KafkaSource.provider_defaults,
        # MSK IAM connections are metered per connection; keep reconnects calm.
        "kafka.reconnect.backoff.ms": "1000",
        "kafka.reconnect.backoff.max.ms": "10000",
    }


@source_registry.register("kafka_cloudera")
class ClouderaKafkaSource(KafkaSource):
    """Cloudera Kafka. Typical auth: kerberos (GSSAPI) or mtls."""

    provider_defaults = {
        **KafkaSource.provider_defaults,
        "kafka.sasl.kerberos.service.name": "kafka",
    }


@source_registry.register("kafka_generic")
class GenericKafkaSource(KafkaSource):
    """Any other Kafka-compatible cluster (Confluent, Redpanda, on-prem)."""
