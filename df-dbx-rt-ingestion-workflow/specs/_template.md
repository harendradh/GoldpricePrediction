---
# ============================================================================
# Functional Specification — machine-readable contract (consumed by
# `dfx job add`). Everything below the closing '---' is prose for humans/AI.
# ============================================================================
job:
  name: <JOB_NAME>                 # kebab-case, e.g. gbs-auth-platform-b-orders
  domain: <DOMAIN>                 # e.g. gbs_auth
  platform: <PLATFORM>             # e.g. platform_b
  description: <one line>

source:
  type: kafka_msk                  # kafka_msk | kafka_cloudera | autoloader
  cluster: msk-primary             # from conf/clusters/
  options:
    startingOffsets: earliest

topics:
  - name: <topic.name.v1>
    format: json                   # parser: json|avro|csv|fixed_width|<platform>.<name>
    schema_subject: <platform>.<entity>
    fields:                        # -> generates resources/schemas/<subject>/v1.ddl
      - { name: <field>, type: string, nullable: false, description: "" }
    mapping:                       # -> generates resources/schemas/<subject>/v1.mapping.yaml
      - { target: <col>, source: <field> }
      # - { target: <col>, expr: "amount * 100", type: "decimal(18,2)" }
    quality:
      - { name: <field>_present, type: not_null, column: <field>, action: dlq }

sink:
  catalog: main
  schema: <DOMAIN>
  table: <target_table>
  mode: merge                      # append | merge
  merge_keys: [<key>]

trigger:
  processingTime: "30 seconds"

tags:
  cost_center: ""
  support_team: ""
---

# <JOB_NAME> — Functional Specification

## Business context
<Why this data is being ingested; consumers; criticality.>

## Data contract
<Upstream producer, message format details, sample payload, volumes/peaks.>

## Mapping notes
<Business meaning of any non-trivial mapping expressions.>

## SLAs & operations
<Freshness SLA, expected lag thresholds, escalation contacts.>
