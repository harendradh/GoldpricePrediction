# Copilot Prompt Library — df-dbx-rt-ingestion-workflow

Curated prompts for common framework tasks. Paste into Copilot Chat with the
repository open so `.github/copilot-instructions.md` is in context. Replace
`<...>` placeholders.

## 1. New common format parser
```
Add a new common parser named "<name>" to
src/dbx_rt_ingestion/parsers/common/<name>_parser.py.
It must subclass BaseParser, implement only parse_payload, register as
"@parser_registry.register('<name>')", set _dfx_error for malformed records
instead of throwing, and preserve all _dfx_* envelope columns.
Options it accepts: <list options and defaults>.
Follow parsers/common/json_parser.py as the reference. Add the module import
to load_builtin_parsers() in parsers/__init__.py and write unit tests in
tests/unit/test_<name>_parser.py covering: happy path, malformed record sets
_dfx_error, envelope preservation.
```

## 2. New platform parser package
```
Create a new platform parser package for platform "<platform>" under
src/dbx_rt_ingestion/parsers/platforms/<platform>/ with a register()
function, following parsers/platforms/platform_a/ exactly.
Implement parser "<platform>.<entity>" that decodes <format description>
using the record layout: <fields with positions/types>.
Business rules: <rules — each violation sets _dfx_error with a
PLATFORM_<X>_* message>. Add the package to _PLATFORM_PACKAGES in
parsers/platforms/__init__.py and write unit tests.
```

## 3. New streaming source
```
Add a streaming source "<name>" in src/dbx_rt_ingestion/sources/<name>.py.
Subclass BaseStreamingSource, register with @source_registry.register,
normalize output to the _dfx_* envelope exactly as sources/kafka.py does,
and document option precedence. Import it in load_builtin_sources().
Include a module spec (docs/specs/module-spec-template.md) and unit tests
for option assembly (no Spark needed — test reader_options()).
```

## 4. New auth provider
```
Add an auth provider "<name>" to src/dbx_rt_ingestion/auth/providers.py.
Subclass BaseAuthProvider, declare required_options, return fully-qualified
kafka.* options from kafka_options(), raise AuthenticationError with the
missing-option list. Never log or echo secret values. Add tests mirroring
tests/unit/test_auth.py.
```

## 5. New metrics publisher
```
Add a metrics publisher "<name>" to
src/dbx_rt_ingestion/observability/publishers.py registering as "<name>".
It must swallow its own exceptions (log-and-continue) — publishers can never
fail the stream. Options: <options>. Publish the event dict as
<target format>. Add unit tests using a fake transport.
```

## 6. Onboard a new application (no code)
```
Author a new application spec conf/apps/<domain>/<platform>.yaml for the
df-dbx-rt-ingestion-workflow framework, modeled on
conf/apps/gbs_auth/platform_a.yaml.
Source: <kafka_msk|kafka_cloudera|autoloader>, cluster <name>,
topics: <topic -> parser/schema/quality/sink mapping>.
Sink: delta table <catalog.schema.table>, mode <append|merge + keys>.
Include DLQ, retry, graceful shutdown marker, audit table, and tags
(cost_center, support_team). Then show the --validate-only command to check it.
```

## 7. New quality rule type
```
Extend src/dbx_rt_ingestion/quality/rules.py with rule type "<type>":
semantics <describe>. Update QualityRuleSpec's Literal in config/models.py,
_violation_condition, the framework-spec rule table, and unit tests for
violated/satisfied/null cases.
```

## 8. Debugging a failing pipeline
```
Given this DFX error and stack trace from a df-dbx-rt-ingestion-workflow app:
<paste>. Using the error-code table in docs/runbooks/operations-runbook.md,
identify the failing component (source/parser/schema/sink), the most likely
root cause, and the spec or environment change that fixes it. Do not suggest
editing framework code for an application-level problem.
```

## Prompting tips
- Name the reference file to imitate — Copilot follows concrete examples.
- Ask for the registry registration, loader import, tests, and doc updates
  in the same prompt; the checklist prevents drift.
- Never accept suggestions containing literal secrets, `if type ==` dispatch,
  or module-level `import pyspark`.
