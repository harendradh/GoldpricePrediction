# ADR-0003: Platform parser isolation

**Status:** Accepted · **Date:** 2026-07-04

## Context
Programs like GBS Auth Data Migration contain multiple platforms (seven for
GBS Auth) with distinct record layouts and business rules that change on
independent schedules. A shared parser codebase would couple their release
cycles and multiply regression risk.

## Decision
Each platform owns a package under `parsers/platforms/<platform>/`,
registering parsers in the `<platform>.<name>` namespace. Platform packages
may depend on `parsers/common/` (format mechanics) but never on each other.
Platforms may ship as separate wheels for fully independent releases.

## Consequences
- A platform layout change is reviewed, tested, and released by that
  platform's owners only.
- CI can scope test/deploy triggers by path (`parsers/platforms/platform_a/**`).
- Cross-platform reuse must be promoted into `common/` deliberately (with a
  module spec), preventing accidental coupling.
- One deployment unit per platform aligns jobs, specs, and parser ownership.
