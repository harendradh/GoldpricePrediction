# df-dbx-rt-ingestion-workflow

Enterprise-grade, **specification-driven** PySpark Structured Streaming
ingestion framework for Databricks. Applications are YAML specs — the
framework supplies sources (AWS MSK Kafka, Cloudera Kafka, Auto Loader),
enterprise authentication (mTLS, SASL_SSL, MSK IAM, Kerberos), a pluggable
parser framework with platform isolation, schema management, data quality,
DLQ/retry/graceful-shutdown reliability, and standardized observability.

```
YAML spec ─► SpecLoader ─► PipelineRunner ─► per-topic pipelines
                            source ─► parser ─► quality ─► DLQ split ─► sink
```

## Quick start (application team) — spec in, pipeline out

1. Write a **functional spec**: copy [specs/_template.md](specs/_template.md)
   to `specs/<domain>/<job>.md` (or run `dfx spec init --domain d --name j`).
   Reference: [platform_b_orders.md](specs/gbs_auth/platform_b_orders.md).
2. Generate the pipeline (or invoke the `add-job` Copilot prompt —
   [.github/prompts/add-job.prompt.md](.github/prompts/add-job.prompt.md)):

   ```bash
   dfx job add --spec specs/<domain>/<job>.md
   ```

   This generates and validates everything: the runtime job config
   (`conf/jobs/`), schema DDL + **schema mapping** files
   (`resources/schemas/<subject>/`), the DAB entry artifact
   (`resources/<domain>/<platform>_databricks.py`), the DAB job resource
   (`resources/<domain>/<job>.job.yml`), and a test (`tests/jobs/`).
3. Deploy — the project-level [databricks.yml](databricks.yml) auto-includes
   every generated job resource:

   ```bash
   databricks bundle deploy -t dev
   ```

No pipeline code is written for a standard onboarding, and generated files
are never edited by hand — change the spec and regenerate with `--force`.

## Quick start (framework developer)

```bash
pip install -e ".[dev,http]"
pytest && ruff check src tests && mypy src
```

Read [developer-onboarding.md](docs/onboarding/developer-onboarding.md).

## Repository map

| Path | Contents |
|---|---|
| `databricks.yml` | project-level DAB bundle (auto-includes `resources/*/*.job.yml`) |
| `specs/` | functional specifications (the only authored file per job) |
| `conf/jobs/` | **generated** runtime job configs (YAML/JSON/TOML supported) |
| `resources/schemas/` | **generated** schema DDL + source→target mapping files |
| `resources/<domain>/` | **generated** `<platform>_databricks.py` + `<job>.job.yml` DAB artifacts |
| `src/dbx_rt_ingestion/cli` | `dfx` CLI (Click) + Jinja2 codegen templates |
| `src/dbx_rt_ingestion/core` | contracts, registry, errors, logging, context |
| `src/dbx_rt_ingestion/config` | spec models, format-agnostic loader, secrets, validation |
| `src/dbx_rt_ingestion/transform` | declarative schema-mapping engine |
| `src/dbx_rt_ingestion/auth` | mTLS / SASL_SSL / MSK IAM / Kerberos providers |
| `src/dbx_rt_ingestion/sources` | kafka_msk, kafka_cloudera, kafka_generic, autoloader |
| `src/dbx_rt_ingestion/parsers` | common format parsers + isolated platform packages |
| `src/dbx_rt_ingestion/schema` | repositories, resolver, evolution/compatibility |
| `src/dbx_rt_ingestion/quality` | declarative data-quality rules |
| `src/dbx_rt_ingestion/sinks` | delta (append/merge, exactly-once), console |
| `src/dbx_rt_ingestion/reliability` | DLQ, retry/backoff, graceful shutdown |
| `src/dbx_rt_ingestion/observability` | query listener, metric events, publishers |
| `src/dbx_rt_ingestion/audit` | run/pipeline audit, lineage basis |
| `src/dbx_rt_ingestion/pipeline` | builder (spec → queries), runner (supervision) |
| `conf/clusters`, `conf/environments` | shared cluster definitions, env overlays |
| `.github/prompts/` | `add-job` Copilot agent prompt (the AI onboarding flow) |
| `docs/specs` | framework spec, module spec template |
| `docs/standards` | coding standards (CI-enforced) |
| `docs/adr` | architecture decision records |
| `docs/prompts` | GitHub Copilot prompt library |
| `docs/runbooks` | operations runbook (error codes, procedures) |
| `.github/copilot-instructions.md` | repository-level Copilot rules |

## Extension model

Every capability is a registered plug-in against an ABC in
[core/interfaces.py](src/dbx_rt_ingestion/core/interfaces.py):

| Extension | Registry | Built-ins |
|---|---|---|
| Sources | `source_registry` | kafka_msk, kafka_cloudera, kafka_generic, autoloader |
| Parsers | `parser_registry` | json, csv, delimited, fixed_width, avro, xml, text, binary, `platform_a.account` |
| Sinks | `sink_registry` | delta, console |
| Auth | `auth_registry` | none, ssl, mtls, sasl_ssl, msk_iam, kerberos |
| Schema repos | `schema_repository_registry` | file, volume, registry |
| Metrics | `publisher_registry` | log, delta, http |

Adding one touches zero framework files — see the
[prompt library](docs/prompts/copilot-prompt-library.md) for guided recipes.

## Key guarantees

- **Exactly-once** to Delta via transactional appends / idempotent MERGE +
  per-pipeline checkpoints.
- **Poison messages never stop the stream** — parsers flag `_dfx_error`,
  records land in the DLQ with full provenance for replay.
- **Row-level lineage** — topic/partition/offset/timestamps persisted with
  every row (`_dfx_*` envelope).
- **Fail-fast startup** — all spec problems reported at once, before any
  query starts.
- **Observability by default** — lag, throughput, latency, watermark, state
  and failure events published per batch (`docs/runbooks` has the alert set).
