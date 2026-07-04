# Framework Specification — df-dbx-rt-ingestion-workflow

**Status:** v0.1.0 · **Owner:** Data Platform Engineering

## 1. Purpose

A specification-driven PySpark Structured Streaming framework for Databricks
that lets thousands of streaming applications be onboarded by writing **YAML
specs, not code**. Initial source support: AWS MSK Kafka; designed for
Cloudera Kafka, Databricks Auto Loader, and future sources with no framework
changes (registry plug-ins).

## 2. Architecture

```
 spec (YAML) ──► SpecLoader ──► AppSpec (pydantic, validated)
                                   │
                              PipelineRunner
                    (logging, audit, listener, supervision)
                                   │
                             PipelineBuilder            one per topic
                                   │
   source_registry ─► StreamingSource.read ─► DataFrame (_dfx_* envelope)
   parser_registry ─► Parser.parse          ─► business columns + _dfx_error
   quality rules   ─► apply_quality_rules   ─► errors/warnings flagged
   DLQ split       ─► valid ─► sink_registry ─► Sink.write (main query)
                     dead  ─► DLQ Delta table          (side query)
```

Component resolution is always: spec `type` string → registry → class →
instance. See `core/registry.py` and `core/interfaces.py`.

### 2.1 Record envelope

Every source normalizes records to these columns, preserved end-to-end:

| Column | Meaning |
|---|---|
| `_dfx_key` | Kafka key / file path |
| `_dfx_value` | raw payload bytes |
| `_dfx_topic` | topic name / input path |
| `_dfx_partition`, `_dfx_offset` | source position (row-level lineage) |
| `_dfx_kafka_timestamp` | source event append time |
| `_dfx_ingest_timestamp` | framework read time |
| `_dfx_error` | parse/quality failure reason (null = healthy) |

This envelope is the basis for lineage, reconciliation, DLQ replay, and
idempotent MERGE writes.

## 3. Specification model

See `config/models.py` (authoritative) and the reference spec
`conf/apps/gbs_auth/platform_a.yaml`. Key blocks: `source` (type, cluster,
topics), per-topic `schema`/`parser`/`quality`/`sink` overrides, app `sink`,
`schema_management`, `reliability` (retry, DLQ, graceful shutdown),
`observability` (publishers, audit), `feature_flags`, `tags`.

Configuration precedence for Kafka reader options (later wins):
provider defaults → auth options → cluster options → source options → topic
options.

Environment overlays: `conf/environments/<env>.yaml` `overrides:` block is
deep-merged onto every app spec; cluster files carry their own
`environments:` block. Placeholders: `${env:NAME}`, `${secret:scope/key}`.

## 4. Extension points

| Extension | ABC | Registry | Built-ins |
|---|---|---|---|
| Source | `StreamingSource` | `source_registry` | kafka_msk, kafka_cloudera, kafka_generic, autoloader |
| Parser | `Parser` | `parser_registry` | json, csv, delimited, fixed_width, avro, xml, text, binary, platform_a.account |
| Sink | `Sink` | `sink_registry` | delta (append/merge), console |
| Auth | `AuthProvider` | `auth_registry` | none, ssl, mtls, sasl_ssl, msk_iam, kerberos |
| Schema repo | `SchemaRepository` | `schema_repository_registry` | file, volume, registry |
| Metrics | `MetricsPublisher` | `publisher_registry` | log, delta, http |

## 5. Schema management

- Repositories store versioned documents: `<subject>/v<major>.(ddl|json|avsc)`.
- `latest` resolves once at startup (deterministic run); pinning recommended
  in prod.
- Evolution gates: `schema/evolution.py` enforces backward/forward/full
  compatibility; wired into deployment tooling and optional startup checks.

## 6. Reliability

- **Exactly-once:** Delta transactional appends + per-pipeline checkpoints;
  MERGE keyed on `merge_keys` is idempotent under batch replay.
- **DLQ:** poison records with full provenance; replay via
  `DeadLetterQueue.replay_statement()` (see runbook).
- **Retry:** exponential backoff with jitter (`reliability/retry.py`);
  runner restarts failed pipelines up to `retry.max_attempts`.
- **Graceful shutdown:** marker file polled by the runner; queries stop after
  the in-flight batch.
- **Checkpoints:** stable path `<checkpoint_root>/<app>__<topic>`; never
  reuse or relocate for a deployed app.

## 7. Observability

`observability/listener.py` attaches a StreamingQueryListener per run and
publishes stable-schema events (`observability/metrics.py`): throughput,
batch duration, latency breakdown, consumer lag, watermark, state-store
rows/memory, offsets, failures. Publishers fan out to log/Delta/HTTP;
enterprise platforms plug in via the registry. Audit records
(`audit/audit.py`) capture run/pipeline lifecycle.

## 8. Deployment

One Databricks job (asset bundle) per platform (`templates/app/databricks.yml`),
`continuous` mode, wheel entry point `dfx-ingest`. Shared framework wheel;
apps ship only specs (and optionally platform parser wheels). CI gates:
ruff, mypy, pytest, spec `--validate-only`, wheel build.

## 9. Non-functional requirements

- Framework modules import without Spark (unit-testable anywhere).
- Startup validation reports **all** problems at once (`config/validation.py`).
- No secrets in specs, logs, or metrics.
- All operational failures map to `DFX-*` error codes (runbook keyed).
