# ADR-0001: Specification-driven application model

**Status:** Accepted · **Date:** 2026-07-04

## Context
Thousands of streaming applications must be migrated across business domains
and platforms. Hand-written Spark jobs do not scale organizationally: every
app re-implements auth, parsing, checkpointing, DLQ, and monitoring with
drift and regression risk.

## Decision
Applications are defined entirely by a YAML specification validated by
pydantic models (`config/models.py`). The framework interprets the spec at
runtime; application repositories contain specs (and optionally platform
parser packages), not pipeline code.

## Consequences
- Onboarding an app = authoring + validating a spec (hours, not weeks).
- Specs are diff-able, reviewable, and machine-validated in CI
  (`dfx-ingest --validate-only`).
- The spec schema is a public contract: changes require backward-compatible
  evolution and a version bump.
- Complex bespoke logic must be expressed as a registered platform parser,
  keeping the escape hatch inside the architecture rather than around it.
