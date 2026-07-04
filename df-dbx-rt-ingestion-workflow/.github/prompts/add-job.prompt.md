---
mode: agent
description: Turn a functional spec in specs/ into a complete, deployable streaming pipeline.
---

# Add a streaming ingestion job

You are working in the df-dbx-rt-ingestion-workflow repository. The user has
written (or will point you at) a functional specification under
`specs/<domain>/<job>.md`. Your task is to make the end-to-end pipeline
ready for deployment. Follow these steps exactly.

## Step 1 — Locate or complete the functional spec
- If the user gave a spec path, read it. If they only described the job in
  chat, create the spec first by copying `specs/_template.md` to
  `specs/<domain>/<job_snake>.md` and filling the YAML front matter from
  their description. Ask for any missing REQUIRED values instead of guessing:
  job name/domain/platform, topic name(s), payload format, field list with
  types, target catalog.schema.table, write mode (+ merge keys when merge).
- The front-matter schema is defined by
  `src/dbx_rt_ingestion/cli/functional_spec.py` — validate your edits
  against it mentally before running the generator.

## Step 2 — Generate the pipeline
Run in the terminal:

    dfx job add --spec specs/<domain>/<job_snake>.md

Use `--force` only when regenerating after a spec change. This generates:
- `conf/jobs/<domain>/<job_snake>.yaml` — runtime job config
- `resources/schemas/<subject>/v1.ddl` — schema per topic
- `resources/schemas/<subject>/v1.mapping.yaml` — source→target mapping
- `resources/<domain>/<platform>_databricks.py` — DAB entry artifact
- `resources/<domain>/<job_snake>.job.yml` — DAB job resource (auto-included
  by the project-level `databricks.yml`)
- `tests/jobs/test_<job_snake>.py` — config validation test

## Step 3 — Verify
1. The command's built-in validation must print `VALID`.
2. Run `python -m pytest tests/jobs/test_<job_snake>.py -q` and confirm green.
3. If the spec references a new Kafka cluster, create
   `conf/clusters/<name>.yaml` (copy `msk-primary.yaml`) before validating.

## Step 4 — Report
Show the user: the list of generated files, the validation output, and the
deploy command (`databricks bundle deploy -t dev`). Never edit generated
files by hand — change the functional spec and regenerate; never put secrets
in any file (use `${secret:scope/key}`).

## Custom parsing
If the payload needs platform-specific decoding (`format` is not a built-in
parser), additionally create the platform parser package following
`.github/copilot-instructions.md` → "When asked to add a new parser", set
`format: <platform>.<name>` in the spec, and regenerate.
