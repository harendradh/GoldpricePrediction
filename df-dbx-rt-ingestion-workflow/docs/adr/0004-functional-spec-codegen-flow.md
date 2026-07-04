# ADR-0004: Functional-spec codegen flow (dfx CLI + add-job prompt)

**Status:** Accepted · **Date:** 2026-07-04 · Supersedes the copy-a-template
onboarding flow from the first cut.

## Context
The first design asked application teams to hand-author runtime job configs
and copy a per-app bundle template. That coupled authoring detail (Kafka
options, checkpoints, DLQ tables, DAB wiring) to every onboarding, and it did
not fit the AI-assisted flow the organization standardizes on: a developer
describes WHAT they need; generation produces HOW it runs.

## Decision
Split authoring from runtime with a code-generation layer:

1. **Functional spec** (`specs/<domain>/<job>.md`) — the only authored file:
   YAML front matter (machine contract, validated by pydantic) + markdown
   prose (business context for humans and AI).
2. **`dfx job add`** — a Click CLI rendering Jinja2 templates
   (`src/dbx_rt_ingestion/cli/templates/`) into ALL runtime artifacts:
   job config, schema DDL, schema **mapping file**, generated
   `resources/<domain>/<platform>_databricks.py` DAB entry artifact, DAB job
   resource, and a validation test. Generated files are committed and guarded
   by a CI drift check (`dfx job add` + `git diff --exit-code`).
3. **`.github/prompts/add-job.prompt.md`** — a single Copilot agent prompt
   that drives the whole flow conversationally (complete the spec, run the
   generator, verify, report).
4. **Project-level `databricks.yml`** auto-includes
   `resources/*/*.job.yml`, so a generated job is deployable with
   `databricks bundle deploy` and zero bundle edits.

## Config format
YAML stays the default serialization: it is the DAB-native format and the
most Copilot-legible. The real contract is the pydantic model layer, so the
loader is format-agnostic (`.yaml`/`.json`/`.toml` by extension) — teams that
prefer TOML for flat configs or JSON for machine-generated configs can use
them without framework changes. A Python-DSL spec was rejected: specs must be
diffable/reviewable by non-engineers and safely generatable by AI.

## Consequences
- Onboarding = one markdown file + one command (or one prompt).
- Hand-editing generated files is prohibited; the functional spec is the
  source of truth and regeneration is idempotent (unchanged output = skip).
- The generator, not each team, encodes conventions (checkpoint layout, DLQ
  naming, audit tables) — convention changes ship as template changes.
- Schema mappings become first-class reviewable artifacts
  (`resources/schemas/<subject>/v1.mapping.yaml`) applied at runtime by
  `transform/mapping.py`.
