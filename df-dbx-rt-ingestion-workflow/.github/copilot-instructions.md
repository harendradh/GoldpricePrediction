# GitHub Copilot Instructions — df-dbx-rt-ingestion-workflow

This repository is an enterprise, **specification-driven** PySpark Structured
Streaming framework for Databricks. Follow these rules for every suggestion.

## Architecture rules (non-negotiable)

1. **Spec-driven, configuration over code.** Behavior comes from YAML specs
   validated by pydantic models in `src/dbx_rt_ingestion/config/models.py`.
   Never hard-code topics, tables, credentials, paths, or environments.
2. **Registry pattern for all extension points.** New sources, parsers, sinks,
   auth providers, schema repositories, and metric publishers are added by
   `@<registry>.register("name")` on a class implementing the matching ABC in
   `core/interfaces.py`. Never add `if type == "x"` dispatch chains.
3. **Lazy PySpark imports.** Import `pyspark` only inside methods or under
   `TYPE_CHECKING`. Module import must succeed without a Spark runtime (this
   is what makes unit tests fast and CI cheap).
4. **Parsers never throw on bad data.** Malformed records get `_dfx_error`
   set and flow to the DLQ. Preserve every `_dfx_*` envelope column
   (see `parsers/base.py: ENVELOPE_COLUMNS`).
5. **Platform isolation.** Platform-specific logic lives only under
   `parsers/platforms/<platform>/` and registers dotted names
   (`platform_a.account`). Common format logic lives in `parsers/common/`.
6. **Secrets** are always `${secret:scope/key}` placeholders in specs,
   resolved by `config/secrets.py`. Never suggest literal credentials.
7. **Errors** use the `FrameworkError` hierarchy in `core/exceptions.py`
   with an `error_code` and structured `context` dict.
8. **Observability must never break the stream.** Listeners and publishers
   catch and log their own exceptions.

## Code style

- Python 3.10+, full type hints, `from __future__ import annotations`.
- Docstring on every module, class, and public function; explain the
  contract, not the implementation.
- Line length 100 (ruff). Naming: modules `snake_case`, classes `PascalCase`,
  registry names `snake_case` (dotted for platform parsers).
- No mutable default arguments; use `Field(default_factory=...)` in pydantic.
- Tests in `tests/unit/` mirror the package path; Spark-dependent tests call
  `pytest.importorskip("pyspark")` and carry the `spark` marker.

## When asked to add a new parser

1. Create `src/dbx_rt_ingestion/parsers/common/<name>_parser.py` (or
   `parsers/platforms/<platform>/<name>_parser.py`).
2. Subclass `BaseParser`, implement only `parse_payload(df, ctx)`.
3. Register: `@parser_registry.register("<name>")`.
4. For platform parsers: add the module import to the platform package's
   `register()` function.
5. Add unit tests + update `docs/specs/framework-spec.md` parser table.

## When asked to add a new source / sink / auth provider / publisher

Same shape: subclass the ABC (`StreamingSource`, `Sink`, `AuthProvider`,
`MetricsPublisher`), register in the matching registry, import it from the
module's `load_builtin_*()` loader, add tests, update the spec docs.

## When asked to onboard a new job (USE THE PROMPT)

Follow `.github/prompts/add-job.prompt.md`. Never hand-write runtime
artifacts. The flow is always:
1. Author/complete the functional spec `specs/<domain>/<job>.md`
   (front-matter schema: `src/dbx_rt_ingestion/cli/functional_spec.py`).
2. Run `dfx job add --spec specs/<domain>/<job>.md`.
3. Verify the printed `VALID` line and run the generated test.

Files under `conf/jobs/`, `resources/` and `tests/jobs/` are GENERATED —
never edit them directly; change the spec and regenerate with `--force`.

## Reference implementations (imitate these)

- Parser: `parsers/common/json_parser.py`, platform example:
  `parsers/platforms/platform_a/account_parser.py`
- Source: `sources/kafka.py` (option precedence pattern)
- Auth: `auth/providers.py`
- Functional spec: `specs/gbs_auth/platform_b_orders.md`
- Codegen templates: `src/dbx_rt_ingestion/cli/templates/`
