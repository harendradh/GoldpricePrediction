# Developer Onboarding — df-dbx-rt-ingestion-workflow

## Day 1: environment
```bash
git clone <repo-url> && cd df-dbx-rt-ingestion-workflow
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,http]"
pytest                       # all unit tests should pass without Spark
ruff check src tests && mypy src
```

## Reading order
1. `docs/specs/framework-spec.md` — architecture + record envelope
2. `conf/apps/gbs_auth/platform_a.yaml` — what an application IS here
3. `core/interfaces.py` + `core/registry.py` — the extension model
4. `pipeline/builder.py` — how a spec becomes running queries
5. `docs/standards/coding-standards.md` — before your first PR

## Your first tasks (in order)
1. **Author a spec** for a fictional app; make `--validate-only` pass:
   `dfx-ingest --spec <your spec> --env dev --conf-dir conf --validate-only`
2. **Break it** — wrong parser name, missing schema — and read the error
   messages; this is what app teams will experience.
3. **Write a parser**: use prompt #1 or #2 from
   `docs/prompts/copilot-prompt-library.md`. Tests first.
4. **Run the smoke pipeline** on a dev Databricks workspace using the
   console sink and a dev topic.

## Copilot setup
- The repo ships `.github/copilot-instructions.md`; keep it open in your
  first sessions to learn the rules Copilot is following.
- Use the prompt library verbatim before writing your own prompts.
- Review every suggestion against: registry pattern? lazy pyspark import?
  `_dfx_error` instead of raise? no secrets?

## Key invariants you must never break
- Envelope columns `_dfx_*` survive every stage.
- Checkpoint paths are stable per deployed app.
- Parsers don't throw on data; observability never breaks the stream.
- Specs contain no secrets and no environment-specific literals (use
  overlays and placeholders).

## Who owns what
- `core/`, `config/`, `pipeline/`, `observability/`: framework team (2 approvals)
- `parsers/platforms/<x>/`: platform x owners
- `conf/apps/<domain>/`: application/domain teams
