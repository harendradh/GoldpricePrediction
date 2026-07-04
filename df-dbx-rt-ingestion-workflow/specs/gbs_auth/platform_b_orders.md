---
job:
  name: gbs-auth-platform-b-orders
  domain: gbs_auth
  platform: platform_b
  description: Platform B order events from AWS MSK into the auth lakehouse.

source:
  type: kafka_msk
  cluster: msk-primary
  options:
    startingOffsets: earliest
    maxOffsetsPerTrigger: "500000"

topics:
  - name: gbs-auth.platform-b.orders.v1
    format: json
    schema_subject: platform_b.orders
    fields:
      - { name: ord_id, type: string, nullable: false, description: "Order identifier" }
      - { name: cust_id, type: string, nullable: false, description: "Customer identifier" }
      - { name: amt, type: "decimal(18,4)", description: "Order amount, source currency" }
      - { name: fx_rate, type: "decimal(10,6)", description: "FX rate to USD at order time" }
      - { name: status_cd, type: string, description: "Order status code" }
      - { name: order_ts, type: timestamp, description: "Order event time" }
    mapping:
      - { target: order_id, source: ord_id }
      - { target: customer_id, source: cust_id }
      - { target: amount_usd, expr: "amt * fx_rate", type: "decimal(18,2)",
          description: "Amount converted to USD" }
      - { target: status, source: status_cd, default: "UNKNOWN" }
      - { target: order_ts, source: order_ts }
    quality:
      - { name: order_id_present, type: not_null, column: ord_id, action: dlq }
      - { name: valid_status, type: allowed_values, column: status_cd,
          options: { values: [NEW, FILLED, CANCELLED] }, action: warn }

sink:
  catalog: main
  schema: gbs_auth
  table: platform_b_orders
  mode: merge
  merge_keys: [order_id]

trigger:
  processingTime: "30 seconds"

tags:
  cost_center: gbs-auth-migration
  support_team: gbs-streaming-ops
---

# gbs-auth-platform-b-orders — Functional Specification

## Business context
Platform B is one of the seven GBS Auth Data Migration platforms. Order
events feed fraud scoring and settlement reconciliation downstream; the
migration replaces the legacy CDC feed with direct Kafka ingestion.

## Data contract
Producer: Platform B order service (JSON over MSK, one order per message,
~2M messages/day, 5x peaks at market open). Keys are `ord_id`. The producer
guarantees at-least-once delivery, so the sink uses MERGE on `order_id`.

## Mapping notes
`amount_usd` is converted at the order-time FX rate carried in the message
(`amt * fx_rate`) — finance requires conversion at event time, not load time.
Unknown status codes must not block ingestion (warn-level rule, defaulted to
`UNKNOWN` in the target).

## SLAs & operations
Freshness SLA 5 minutes; alert at 15 minutes of growing consumer lag.
Escalation: gbs-streaming-ops (primary), platform_b owners (data issues).
