# Databricks notebook source
# ============================================================
# STREAMING DELAY DIAGNOSTIC  (import into Databricks; cells split on
# the "# COMMAND ----------" markers)
#
# What it proves:
#   1. Whether records are bucketed by EVENT time (correct) or drifting
#      into later windows (window_mismatch = true  -> your bug).
#   2. Where the delay lives: source / consume / total lag.
#   3. True per-partition Kafka backlog for THIS stream.
#
# EDIT the 3 spots marked  >>> EDIT <<<
# ============================================================

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType
import json

# COMMAND ----------
# ---- 0. Pin timezone to the zone your business windows are defined in.
#      (UTC is typical for Kafka. Set to "Asia/Kolkata" etc. if your
#       windows are defined in local time.)
spark.conf.set("spark.sql.session.timeZone", "UTC")            # >>> EDIT <<<
print("session tz:", spark.conf.get("spark.sql.session.timeZone"))

# COMMAND ----------
# ---- 1. Config  >>> EDIT <<<
KAFKA_BOOTSTRAP = "your-broker:9092"
TOPIC           = "your-topic"
WINDOW          = "5 minutes"     # your window size
CHECKPOINT      = "/tmp/diag_checkpoint_" + TOPIC   # throwaway, diagnostic only

# COMMAND ----------
# ---- 2. Read raw stream (NO windowing yet — keep raw timestamps)
raw = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
    .option("subscribe", TOPIC)
    .option("startingOffsets", "latest")
    .load()
)
# raw.timestamp = Kafka ingest time (NOT your business event time)

# COMMAND ----------
# ---- 3. Parse payload & extract the REAL event time  >>> EDIT schema/format <<<
payload_schema = StructType([
    StructField("id",       StringType(), True),
    StructField("event_ts", StringType(), True),   # your source timestamp field
    # ... add your other fields
])

parsed = (
    raw
    .select(
        F.col("timestamp").alias("kafka_ingest_ts"),
        F.from_json(F.col("value").cast("string"), payload_schema).alias("d"),
    )
    .select(
        "kafka_ingest_ts",
        F.col("d.id").alias("id"),
        # If your event_ts is a specific string format, pass it explicitly, e.g.:
        # F.to_timestamp(F.col("d.event_ts"), "yyyy-MM-dd'T'HH:mm:ss.SSSX")
        F.to_timestamp(F.col("d.event_ts")).alias("event_ts"),
    )
)

# COMMAND ----------
# ---- 4. Compute the 3 lag components + window mismatch flag
check = (
    parsed
    .withColumn("processing_ts", F.current_timestamp())
    .withColumn("source_lag_s",
                F.col("kafka_ingest_ts").cast("double") - F.col("event_ts").cast("double"))
    .withColumn("consume_lag_s",
                F.col("processing_ts").cast("double") - F.col("kafka_ingest_ts").cast("double"))
    .withColumn("total_lag_s",
                F.col("processing_ts").cast("double") - F.col("event_ts").cast("double"))
    .withColumn("event_window",
                F.window(F.col("event_ts"), WINDOW).getField("start"))
    .withColumn("processing_window",
                F.window(F.col("processing_ts"), WINDOW).getField("start"))
    .withColumn("window_mismatch",
                F.col("event_window") != F.col("processing_window"))
)

# COMMAND ----------
# ---- 5. Live view: lag + mismatches (fastest sanity check)
q = (
    check.selectExpr(
        "id", "event_ts", "kafka_ingest_ts", "processing_ts",
        "round(source_lag_s,1)  as source_lag_s",
        "round(consume_lag_s,1) as consume_lag_s",
        "round(total_lag_s,1)   as total_lag_s",
        "event_window", "processing_window", "window_mismatch",
    )
    .writeStream
    .format("console")            # or "memory" + queryName to query with SQL
    .option("truncate", False)
    .option("numRows", 50)
    .option("checkpointLocation", CHECKPOINT)
    .trigger(processingTime="30 seconds")
    .start()
)

# COMMAND ----------
# ---- 6. Per-partition Kafka lag for THIS stream (the real backlog).
#      Run this cell repeatedly while the stream above is up.
def print_kafka_lag(query):
    p = query.lastProgress
    if not p or not p.get("sources"):
        print("no progress yet — wait for a batch or two..."); return
    src = p["sources"][0]
    print(f"batchId              : {p.get('batchId')}")
    print(f"batchDuration (ms)   : {p.get('batchDuration')}")
    print(f"inputRowsPerSecond   : {p.get('inputRowsPerSecond')}")
    print(f"processedRowsPerSecond: {p.get('processedRowsPerSecond')}")
    try:
        end    = json.loads(src.get("endOffset")    or "{}")
        latest = json.loads(src.get("latestOffset") or "{}")
        total = 0
        for topic, parts in latest.items():
            for part, latest_off in parts.items():
                processed = end.get(topic, {}).get(part, 0)
                lag = latest_off - processed
                total += lag
                print(f"  {topic}-{part:>3}  lag = {lag}")
        print(f"  TOTAL LAG = {total}")
    except Exception as ex:
        print("offset parse issue:", ex)
        print("raw endOffset:", src.get("endOffset"))
        print("raw latestOffset:", src.get("latestOffset"))

print_kafka_lag(q)

# COMMAND ----------
# ---- 7. Full progress dump (batchDuration, durationMs.addBatch, rates, offsets)
print(json.dumps(q.lastProgress, indent=2, default=str))
# Watch:
#   batchDuration            > trigger interval        -> falling behind (Cause C)
#   processedRowsPerSecond   < inputRowsPerSecond       -> backlog growing (Cause C)
#   durationMs.addBatch      dominates                  -> slow sink (Cause E)
#   TOTAL LAG grows each run                            -> Spark behind Kafka (Cause C)
#   window_mismatch = true (cell 5)                     -> wrong window column (Cause A)

# COMMAND ----------
# ============================================================
# PART B — VALIDATE YOUR STATS / MONITORING DELTA TABLE
#   Table shape (long format, one row per window type per slice):
#     table_name | start_ts | end_window_ts | count | window_type
#   window_type in {FIVE_MINUTES, FIFTEEN_MINUTES, SIXTY_MINUTES}
#   SIXTY_MINUTES = cumulative count within the clock hour.
#
#   >>> EDIT <<< set STATS_TABLE, and confirm SIXTY reset mode in cell B4.
# ============================================================
STATS_TABLE = "db.your_stats_table"          # >>> EDIT <<<
spark.conf.set("spark.sql.diag.statsTable", STATS_TABLE)

# COMMAND ----------
# ---- B1. Ordered listing: all window types together, per slice, by size
display(spark.sql(f"""
    SELECT table_name, start_ts, end_window_ts, count, window_type
    FROM {STATS_TABLE}
    ORDER BY
      end_window_ts,
      CASE upper(window_type)
        WHEN 'FIVE_MINUTES'    THEN 1
        WHEN 'FIFTEEN_MINUTES' THEN 2
        WHEN 'SIXTY_MINUTES'   THEN 3
        ELSE 99
      END
"""))

# COMMAND ----------
# ---- B2. Pivot: one row per 5-min slice, each window type as a column
display(spark.sql(f"""
    SELECT
      end_window_ts,
      MAX(CASE WHEN upper(window_type)='FIVE_MINUTES'    THEN count END) AS five_min,
      MAX(CASE WHEN upper(window_type)='FIFTEEN_MINUTES' THEN count END) AS fifteen_min,
      MAX(CASE WHEN upper(window_type)='SIXTY_MINUTES'   THEN count END) AS sixty_min
    FROM {STATS_TABLE}
    GROUP BY end_window_ts
    ORDER BY end_window_ts
"""))

# COMMAND ----------
# ---- B3. Validate FIFTEEN_MINUTES = sum of the 3 five-min slices in (T-15, T]
#      diff should be 0. Non-zero = missed / double-counted slice.
display(spark.sql(f"""
    WITH five AS (
      SELECT end_window_ts, count AS c5
      FROM {STATS_TABLE} WHERE upper(window_type)='FIVE_MINUTES'
    ),
    expected AS (
      SELECT f.end_window_ts, SUM(prev.c5) AS expected_fifteen
      FROM five f
      JOIN five prev
        ON prev.end_window_ts >  f.end_window_ts - INTERVAL 15 MINUTES
       AND prev.end_window_ts <= f.end_window_ts
      GROUP BY f.end_window_ts
    )
    SELECT
      e.end_window_ts,
      e.expected_fifteen,
      s.count AS actual_fifteen,
      e.expected_fifteen - s.count AS diff
    FROM expected e
    JOIN {STATS_TABLE} s
      ON s.end_window_ts = e.end_window_ts
     AND upper(s.window_type)='FIFTEEN_MINUTES'
    ORDER BY e.end_window_ts
"""))

# COMMAND ----------
# ---- B4. Validate cumulative SIXTY_MINUTES = running sum of FIVE within the hour.
#      >>> If SIXTY resets on the CLOCK HOUR (22:00, 23:00...): keep as-is.
#      >>> If SIXTY is a ROLLING 60-min window: use the RANGE variant below.
display(spark.sql(f"""
    WITH five AS (
      SELECT start_ts, end_window_ts, count AS c5
      FROM {STATS_TABLE} WHERE upper(window_type)='FIVE_MINUTES'
    ),
    running AS (
      SELECT
        end_window_ts,
        SUM(c5) OVER (
          PARTITION BY date_trunc('HOUR', start_ts)      -- clock-hour reset
          ORDER BY end_window_ts
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS expected_sixty
      FROM five
    )
    SELECT
      r.end_window_ts,
      r.expected_sixty,
      s.count AS actual_sixty,
      r.expected_sixty - s.count AS diff
    FROM running r
    JOIN {STATS_TABLE} s
      ON s.end_window_ts = r.end_window_ts
     AND upper(s.window_type)='SIXTY_MINUTES'
    ORDER BY r.end_window_ts
"""))

# COMMAND ----------
# ---- B4-rolling. Use INSTEAD of B4 if SIXTY is a rolling 60-min window.
# display(spark.sql(f"""
#     WITH five AS (
#       SELECT end_window_ts, count AS c5
#       FROM {STATS_TABLE} WHERE upper(window_type)='FIVE_MINUTES'
#     ),
#     running AS (
#       SELECT end_window_ts,
#         SUM(c5) OVER (
#           ORDER BY CAST(end_window_ts AS timestamp)
#           RANGE BETWEEN INTERVAL 60 MINUTES PRECEDING AND CURRENT ROW
#         ) AS expected_sixty
#       FROM five
#     )
#     SELECT r.end_window_ts, r.expected_sixty, s.count AS actual_sixty,
#            r.expected_sixty - s.count AS diff
#     FROM running r
#     JOIN {STATS_TABLE} s
#       ON s.end_window_ts = r.end_window_ts AND upper(s.window_type)='SIXTY_MINUTES'
#     ORDER BY r.end_window_ts
# """))

# COMMAND ----------
# ---- B5. PASS/FAIL summary — counts mismatched rows across both checks.
summary = spark.sql(f"""
    WITH five AS (
      SELECT start_ts, end_window_ts, count AS c5
      FROM {STATS_TABLE} WHERE upper(window_type)='FIVE_MINUTES'
    ),
    fifteen_chk AS (
      SELECT f.end_window_ts, SUM(prev.c5) AS expected, 'FIFTEEN_MINUTES' AS wt
      FROM five f JOIN five prev
        ON prev.end_window_ts >  f.end_window_ts - INTERVAL 15 MINUTES
       AND prev.end_window_ts <= f.end_window_ts
      GROUP BY f.end_window_ts
    ),
    sixty_chk AS (
      SELECT end_window_ts,
        SUM(c5) OVER (PARTITION BY date_trunc('HOUR', start_ts)
                      ORDER BY end_window_ts
                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS expected,
        'SIXTY_MINUTES' AS wt
      FROM five
    ),
    expected_all AS (
      SELECT * FROM fifteen_chk UNION ALL SELECT * FROM sixty_chk
    )
    SELECT e.wt AS window_type,
           COUNT(*)                                            AS slices_checked,
           SUM(CASE WHEN e.expected <> s.count THEN 1 ELSE 0 END) AS mismatches
    FROM expected_all e
    JOIN {STATS_TABLE} s
      ON s.end_window_ts = e.end_window_ts
     AND upper(s.window_type) = e.wt
    GROUP BY e.wt
""")
display(summary)
total_mismatches = summary.agg({"mismatches": "sum"}).collect()[0][0] or 0
print("RESULT:", "PASS ✅ (no delay / count drift)" if total_mismatches == 0
      else f"FAIL ❌ — {total_mismatches} mismatched slice(s); inspect B3/B4 for the gap")

# COMMAND ----------
# ---- 8. Cleanup when done
# q.stop()
# dbutils.fs.rm(CHECKPOINT, recurse=True)
