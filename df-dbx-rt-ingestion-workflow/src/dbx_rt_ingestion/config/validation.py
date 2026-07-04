"""Startup validation: fail fast, fail loud, fail with a runbook-ready message.

Beyond pydantic's structural validation, this module checks cross-cutting
semantics before any stream starts: registry membership for every ``type``
reference, checkpoint path sanity, DLQ configuration, and per-topic schema
references. All problems are collected and reported together.
"""

from __future__ import annotations

from dbx_rt_ingestion.config.models import AppSpec
from dbx_rt_ingestion.core.exceptions import SpecValidationError


def validate_app_spec(spec: AppSpec) -> None:
    """Validate registry references and semantics; raise with all findings."""

    # Imported here so registration side effects have run and to avoid cycles.
    from dbx_rt_ingestion.auth.providers import auth_registry  # noqa: F401
    from dbx_rt_ingestion.observability.publishers import publisher_registry
    from dbx_rt_ingestion.parsers import load_builtin_parsers
    from dbx_rt_ingestion.parsers.base import parser_registry
    from dbx_rt_ingestion.schema.repository import schema_repository_registry
    from dbx_rt_ingestion.sinks import load_builtin_sinks
    from dbx_rt_ingestion.sinks.base import sink_registry
    from dbx_rt_ingestion.sources import load_builtin_sources
    from dbx_rt_ingestion.sources.base import source_registry

    load_builtin_parsers()
    load_builtin_sinks()
    load_builtin_sources()

    problems: list[str] = []

    if spec.source.type not in source_registry:
        problems.append(
            f"source.type '{spec.source.type}' not registered "
            f"(available: {source_registry.names()})"
        )

    sinks = [spec.sink] + [t.sink for t in spec.source.topics if t.sink]
    for sink in sinks:
        if sink.type not in sink_registry:
            problems.append(
                f"sink.type '{sink.type}' not registered (available: {sink_registry.names()})"
            )

    if spec.schema_management.repository not in schema_repository_registry:
        problems.append(
            f"schema_management.repository '{spec.schema_management.repository}' "
            f"not registered (available: {schema_repository_registry.names()})"
        )

    for publisher in spec.observability.publishers:
        if publisher.type not in publisher_registry:
            problems.append(
                f"observability publisher '{publisher.type}' not registered "
                f"(available: {publisher_registry.names()})"
            )

    seen_topics: set[str] = set()
    for topic in spec.source.topics:
        if topic.name in seen_topics:
            problems.append(f"duplicate topic '{topic.name}'")
        seen_topics.add(topic.name)

        if topic.parser.type not in parser_registry:
            problems.append(
                f"topic '{topic.name}': parser '{topic.parser.type}' not registered "
                f"(available: {parser_registry.names()})"
            )
        needs_schema = topic.parser.type in {"json", "avro", "csv", "delimited"}
        if needs_schema and topic.schema_ref is None:
            problems.append(
                f"topic '{topic.name}': parser '{topic.parser.type}' requires a schema"
            )

    if not spec.checkpoint_root.strip():
        problems.append("checkpoint_root must not be empty")

    if spec.reliability.dlq.enabled and not (
        spec.reliability.dlq.table or spec.sink.table
    ):
        problems.append("dlq.enabled requires dlq.table or a table-based sink to derive it")

    if problems:
        raise SpecValidationError(
            f"Application spec '{spec.name}' failed startup validation "
            f"({len(problems)} problem(s))",
            context={"problems": problems},
        )
