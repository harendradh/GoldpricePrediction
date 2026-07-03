# Spark Structured Streaming — Window Delay Troubleshooting Guide (Databricks)

**Symptom:** Records whose source/event time is in one window (e.g. `22:55`) are being
written into the *next* window (e.g. `23:00–23:05`).

**Goal:** Prove whether records are processed on time, find the root cause, and fix it.

---

## 0. Mental model — the 3 timestamps

Every streaming record has three different times. Confusing them is the #1 cause of this bug.

| Timestamp | What it means | Where it comes from |
|---|---|---|
| **Event time** | When the business event actually happened | A field *inside* your message payload (e.g. `event_ts`) |
| **Ingest time** | When Kafka received the record | The Kafka `timestamp` column |
| **Processing time** | When Spark ran the micro-batch that handled it | `current_timestamp()` on the cluster |

**Windows must be built on EVENT time.** If your window is built on processing time
(or Kafka ingest time), a slow/late batch shoves a `22:55` event into the `23:00` window —
exactly your symptom.

---

## 1. Decision tree (read this first)

```
Is your window() built on the event-time column from the payload?
│
├─ NO  ──────────────────────────────► ROOT CAUSE A: wrong window column   → Fix in §5.1
│
└─ YES
   │
   Is spark.sql.session.timeZone the same zone your windows are defined in?
   │
   ├─ NO ───────────────────────────► ROOT CAUSE B: timezone shift          → Fix in §5.2
   │
   └─ YES
      │
      Run the lag script (§3). Is consume_lag / Kafka lag GROWING batch over batch?
      │
      ├─ YES ────────────────────────► ROOT CAUSE C: Spark falling behind    → Fix in §5.3
      │
      └─ NO
         │
         Do you have a watermark, and is late data being dropped or misplaced?
         │
         ├─ NO watermark ────────────► ROOT CAUSE D: no/late watermark       → Fix in §5.4
         │
         └─ Sink/trigger issue ──────► ROOT CAUSE E: slow sink / trigger      → Fix in §5.5
```

---

## 2. Step-by-step plan

1. **Measure** — run the diagnostic notebook (`diagnostic_notebook.py`) to quantify lag and
   detect window mismatches. (§3)
2. **Locate** — use the decision tree + `lastProgress` metrics to find which of A–E you have. (§4)
3. **Fix** — apply the matching fix. (§5)
4. **Verify** — re-run the diagnostic; confirm `window_mismatch` count ≈ 0 and lag is stable. (§6)
5. **Monitor** — keep a lightweight lag monitor running in production. (§7)

---

## 3. Measure — run the diagnostic notebook

Import `diagnostic_notebook.py` into Databricks (the `# COMMAND ----------` markers become cells).
Edit the 3 marked spots: **broker/topic**, **payload_schema**, **timestamp format**.

It produces:
- **`window_mismatch`** — `true` when a record's event-time window ≠ its processing-time window.
  Many `true` rows = you are (accidentally) bucketing by processing time. **This is the key signal.**
- **`source_lag_s`** — event → Kafka (producer/upstream lag).
- **`consume_lag_s`** — Kafka → Spark (backlog / throughput lag). **Watch this one closely.**
- **`total_lag_s`** — end-to-end latency.
- **Per-partition Kafka lag** — from `lastProgress`, the true backlog for your stream.

---

## 4. Locate — how to read the metrics

| What you see | Meaning | Root cause |
|---|---|---|
| Many `window_mismatch = true`, but lag is small | Windowing on processing time | **A** (§5.1) |
| Windows are off by a fixed whole-hour amount (e.g. +5:30) | Timezone offset | **B** (§5.2) |
| `consume_lag_s` grows every batch; `batchDuration` > trigger interval | Spark can't keep up | **C** (§5.3) |
| Late records dropped, or state/memory ballooning | Missing/short watermark | **D** (§5.4) |
| Batch time dominated by `addBatch` (sink write) | Slow sink | **E** (§5.5) |

Key `lastProgress` fields (printed by the notebook):
- `batchDuration` > your trigger interval → permanent drift.
- `processedRowsPerSecond` < `inputRowsPerSecond` → backlog growing.
- `durationMs.addBatch` large → sink is the bottleneck.
- `sources[].endOffset` vs `sources[].latestOffset` → per-partition Kafka lag.

---

## 5. Fixes

### 5.1 ROOT CAUSE A — window built on the wrong column (most common)

```python
# ❌ WRONG — buckets by when Spark runs → your exact symptom
.groupBy(window(current_timestamp(), "5 minutes"))
# ❌ ALSO WRONG — buckets by Kafka ingest time, not business event time
.groupBy(window(col("timestamp"), "5 minutes"))

# ✅ RIGHT — bucket by the event timestamp parsed from the payload
.groupBy(window(col("event_ts"), "5 minutes"))
```
Extract `event_ts` from the message value with `from_json` + `to_timestamp` (see §5.6 full pipeline).

### 5.2 ROOT CAUSE B — timezone mismatch

Kafka/source is usually **UTC**; a Databricks cluster may default to local time (e.g. IST +5:30),
which shifts every window boundary.

```python
# Pin the session timezone to the zone your windows are DEFINED in.
spark.conf.set("spark.sql.session.timeZone", "UTC")   # or "Asia/Kolkata"
```
Also make sure your `to_timestamp` format string matches the source string exactly, e.g.
`to_timestamp(col("d.event_ts"), "yyyy-MM-dd'T'HH:mm:ss.SSSX")` for ISO-8601 with zone.

### 5.3 ROOT CAUSE C — Spark falling behind Kafka (throughput)

Symptoms: growing `consume_lag_s`, growing per-partition lag, `batchDuration` > trigger.

Fixes (try in order):
1. **Cap batch size** so batches finish within the trigger interval:
   ```python
   .option("maxOffsetsPerTrigger", 500000)   # tune to your throughput
   ```
2. **Add parallelism** — Kafka partitions should be ≥ total cores. If the topic has few
   partitions, Spark can't parallelize the read. Increase topic partitions or repartition
   after read for the heavy transforms.
3. **Scale the cluster** — more workers / autoscaling; enable
   `spark.databricks.streaming.autoscaling` on Jobs clusters if available.
4. **Shorten the trigger** so windowing is decoupled from batch cadence:
   ```python
   .trigger(processingTime="30 seconds")
   ```
5. Remove expensive per-record work (UDFs, wide shuffles) from the streaming path.

### 5.4 ROOT CAUSE D — missing / wrong watermark

```python
.withWatermark("event_ts", "10 minutes")   # same column used in window()
```
- Set the delay to your realistic worst-case lateness (use the p95 lag from the diagnostic).
- The watermark column **must** equal the `window()` column.
- Too short → legitimately late records dropped. Too long → higher output latency & more state.

### 5.5 ROOT CAUSE E — slow sink / trigger cadence

- If writing to Delta and `durationMs.addBatch` is high: you likely have a **small-files** problem.
  Enable auto-optimize / periodic `OPTIMIZE`, and don't over-partition the output table.
- Match trigger interval to actual processing capacity; don't set trigger == window size
  (any late batch then shifts data into the next window).
- Ensure a **dedicated checkpoint** per query (see §5.6).

### 5.6 The corrected production pipeline (template)

```python
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

spark.conf.set("spark.sql.session.timeZone", "UTC")   # §5.2

schema = StructType([
    StructField("id",       StringType(), True),
    StructField("event_ts", StringType(), True),   # <-- your source event time field
    # ... other fields
])

raw = (spark.readStream.format("kafka")
       .option("kafka.bootstrap.servers", "<broker>:9092")
       .option("subscribe", "<topic>")
       .option("startingOffsets", "latest")
       .option("maxOffsetsPerTrigger", 500000)        # §5.3
       .load())

parsed = (raw
    .select(F.from_json(F.col("value").cast("string"), schema).alias("d"))
    .select("d.*")
    .withColumn("event_ts", F.to_timestamp(F.col("event_ts")))   # parse event time
)

agg = (parsed
    .withWatermark("event_ts", "10 minutes")               # §5.4
    .groupBy(F.window(F.col("event_ts"), "5 minutes"))     # §5.1 — EVENT time
    .agg(F.count("*").alias("cnt"))
    .select(F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "cnt")
)

query = (agg.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "/mnt/checkpoints/<topic>_5min_agg")  # dedicated!
    .trigger(processingTime="1 minute")                    # §5.5
    .toTable("db.window_counts"))
```

---

## 6. Verify the fix

Re-run the diagnostic notebook and confirm:
- `window_mismatch` count ≈ **0**.
- `consume_lag_s` / per-partition lag is **stable** (not growing) across batches.
- `batchDuration` < trigger interval.
- A `22:55` event lands in the `22:55–23:00` window in the output table.

Spot check:
```python
%sql
SELECT window_start, window_end, cnt
FROM db.window_counts
ORDER BY window_start DESC
LIMIT 20;
```

---

## 7. Keep monitoring in production

Attach a `StreamingQueryListener` (or scrape `lastProgress` on a schedule) to alert when
lag grows. Minimal version:

```python
from pyspark.sql.streaming import StreamingQueryListener

class LagListener(StreamingQueryListener):
    def onQueryStarted(self, e): pass
    def onQueryTerminated(self, e): pass
    def onQueryProgress(self, e):
        p = e.progress
        inp = p.numInputRows
        rate_in  = p.inputRowsPerSecond or 0
        rate_out = p.processedRowsPerSecond or 0
        if rate_in > rate_out and inp > 0:
            print(f"[LAG WARNING] in={rate_in:.0f}/s out={rate_out:.0f}/s "
                  f"batchId={p.batchId} rows={inp}")

spark.streams.addListener(LagListener())
```

---

## Quick reference — the 5 root causes

| # | Root cause | One-line fix |
|---|---|---|
| A | Window on processing/ingest time | `window(col("event_ts"), ...)` |
| B | Timezone shift | `spark.conf.set("spark.sql.session.timeZone", "UTC")` |
| C | Spark behind Kafka | `maxOffsetsPerTrigger` + more partitions/cores + shorter trigger |
| D | No/short watermark | `.withWatermark("event_ts", "10 minutes")` |
| E | Slow sink / trigger == window | OPTIMIZE Delta, dedicated checkpoint, trigger < window |
