# Operations Runbook — df-dbx-rt-ingestion-workflow

Audience: application operations and alerting teams.

## 1. What runs where
- One Databricks continuous job per platform (`dfx-<env>-<app>`), wheel entry
  point `dfx-ingest`, one streaming query per topic named `<app>__<topic>`
  plus a `__dlq` side query per topic when DLQ is enabled.
- Checkpoints: `<checkpoint_root>/<query name>` — never delete or relocate
  without a coordinated replay plan.

## 2. Error code table

| Code | Component | Typical cause | First response |
|---|---|---|---|
| DFX-1000/1001 | Spec/config | bad YAML, unknown registry type, missing field | fix spec; run `--validate-only` |
| DFX-1002 | Secrets | secret scope/key missing or no permission | verify scope ACLs, key name |
| DFX-2000 | Auth | expired cert/keytab, wrong mechanism, IAM role | check credential material dates; test with kafka console client |
| DFX-3000 | Source | brokers unreachable, topic deleted, ACLs | network path + topic existence + consumer ACLs |
| DFX-4000 | Parser | contract bug (bad data goes to DLQ, not here) | escalate to platform owner |
| DFX-5000/5001 | Schema | subject/version missing, incompatible evolution | check repository contents; review compatibility mode |
| DFX-6000 | Sink | table perms, schema mismatch on target | check UC grants, target DDL |
| DFX-7000/7001 | Runner | pipeline failed and retries exhausted | read the last query exception in driver logs |

## 3. Standard procedures

### 3.1 Graceful shutdown / restart
1. Create the marker file configured at `reliability.graceful_shutdown_marker`
   (e.g. `touch` it on the UC volume).
2. Wait for the audit event `run_stopped` (reason `graceful_shutdown`).
3. Remove the marker BEFORE restarting the job, or it stops again.

### 3.2 Consumer lag alert
1. Check `input_rows_per_second` vs `processed_rows_per_second` in metrics.
2. If processing-bound: raise cluster size or lower `maxOffsetsPerTrigger`
   per batch (spec change, redeploy).
3. If a poison-message storm: check DLQ growth (`SELECT error, count(*) ...`).

### 3.3 DLQ triage & replay
1. Inspect: `SELECT error, count(*) FROM <dlq_table> GROUP BY error`.
2. Root-cause with the platform owner (payload column holds raw bytes).
3. After a parser/schema fix is deployed, replay by producing the dead
   records back to a replay topic (query from
   `DeadLetterQueue.replay_statement()`), then archive the replayed rows.

### 3.4 Full data replay (reprocessing from Kafka)
1. Stop the app gracefully (3.1).
2. Deploy a NEW checkpoint_root (never reuse) and set
   `startingOffsets` to the required timestamp/offset JSON in the topic
   options.
3. Ensure the sink is idempotent for the window: merge mode is safe;
   append mode requires target dedup or a swap table.

### 3.5 Failed batch / restart loop
- Runner restarts a failed pipeline `retry.max_attempts` times with
  exponential backoff, then fails the job (Databricks `continuous` mode
  restarts the job). If the loop persists >3 job restarts, page the
  framework team with the DFX code and query exception.

## 4. Monitoring reference
Metric events (`event_type=query_progress`) include: `consumer_lag_offsets`,
`input_rows_per_second`, `processed_rows_per_second`, `batch_duration_ms`,
`add_batch_ms`, `watermark`, `state_rows_total`, `state_memory_bytes`,
`source_start_offsets`/`source_end_offsets`, `output_rows`.
Failures emit `event_type=query_terminated, failed=true`.

Suggested alerts:
- `consumer_lag_offsets` growing for 15 min → warning; 60 min → critical.
- `batch_duration_ms` > trigger interval for 10 consecutive batches.
- any `query_terminated` with `failed=true`.
- DLQ table row growth rate > agreed threshold per app.
