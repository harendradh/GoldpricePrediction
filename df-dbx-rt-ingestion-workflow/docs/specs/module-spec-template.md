# Module Specification — <module name>

> Copy this template for every new framework module or platform parser
> package. Keep it under two pages; link to code for detail.

## Identity
- **Module:** `dbx_rt_ingestion.<package>.<module>`
- **Extension point:** source | parser | sink | auth | schema repo | publisher | n/a
- **Registry name(s):** `<name>` (platform parsers: `<platform>.<name>`)
- **Owner team:**
- **Release unit:** framework wheel | platform wheel `<name>`

## Purpose
One paragraph: what the module does and when a spec should select it.

## Contract
- Implements: `<ABC from core/interfaces.py>`
- Input guarantees it relies on (e.g. `_dfx_*` envelope present).
- Output guarantees it provides (columns, error behavior, idempotency).
- Failure behavior: which `DFX-*` error codes it raises and when it instead
  flags `_dfx_error`.

## Configuration
| Option | Type | Required | Default | Description |
|---|---|---|---|---|
|  |  |  |  |  |

Example spec fragment:

```yaml
parser:
  type: <name>
  options: {}
```

## Observability
Metrics/log events this module contributes beyond the standard set.

## Testing
- Unit tests: `tests/unit/test_<module>.py` (Spark-free where possible)
- Integration tests + fixtures required:
- Performance considerations / limits:

## Open questions / ADR links
