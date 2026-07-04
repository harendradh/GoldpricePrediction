# ADR-0002: Registry pattern for all extension points

**Status:** Accepted · **Date:** 2026-07-04

## Context
The framework must support new sources (Cloudera Kafka, future platforms),
parsers, sinks, auth mechanisms, schema repositories, and monitoring
publishers with minimal change and no regression risk to existing apps.

## Decision
Every extension point is an ABC in `core/interfaces.py` plus a generic
`Registry` (`core/registry.py`). Implementations self-register via a class
decorator; specs select them by name. Built-ins load through explicit
`load_builtin_*()` importers; external packages may register at import time
(entry-point loading is a planned extension).

## Alternatives considered
- **Factory functions with if/elif dispatch:** rejected — every new
  implementation modifies shared code (Open/Closed violation, merge
  conflicts at scale).
- **setuptools entry points only:** deferred — great for third-party wheels,
  but explicit imports are simpler to reason about for the first release and
  work identically on Databricks.

## Consequences
- Adding a connector touches zero framework files (new module + one import
  line in the loader).
- Registry names become a governed namespace; duplicates fail fast at import.
- Startup validation can enumerate available implementations for actionable
  error messages.
