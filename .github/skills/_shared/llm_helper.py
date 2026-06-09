"""Shared LLM helpers · structured-output prompting + finding hydration.

The model gets explicit instructions to cite authoritative references
(OWASP, CWE, PEP, RFC, Effective Java, etc.) in every finding. That way
review comments come pre-formatted with citations engineers can verify
externally rather than just trusting the AI's word.
"""
from __future__ import annotations

from typing import Any, Sequence

from Agents.Core.model import DatabricksClaude, ModelCallConfig, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, Finding, Severity, SkillContext
from skills._shared.standards import Standard

logger = get_logger(__name__)


_FINDING_SCHEMA_INSTRUCTION = """\
## Output contract

You MUST return ONLY a JSON object with this exact shape:

{
  "findings": [
    {
      "rule_id": "namespace.short_name",
      "severity": "BLOCKER" | "MAJOR" | "MINOR" | "NIT",
      "dimension": "correctness | security | performance | architecture | testing | documentation | dependencies | governance | configuration | data_model | api_contract | concurrency | resource_management | error_handling",
      "confidence": 0-100 integer,
      "file": "path/to/file.ext",
      "line_start": int,
      "line_end": int,
      "title": "one-line summary",
      "quote": "the offending 1-3 lines or null",
      "why": "business-terms reason this matters · cite the consequence",
      "fix": "suggested patch in fenced code block, or null",
      "references": ["Authoritative standard 1 — URL", "Authoritative standard 2 — URL"]
    }
  ]
}

## Authoring rules

1. Empty findings list is acceptable when nothing in scope matches.
2. Do not invent `rule_id`s — keep within this skill's namespace.
3. **Every finding MUST include `references`** to at least one authoritative
   standard from the catalog above (OWASP, CWE, PEP, RFC, Effective Java, …).
   Reviewers need verifiable citations, not opinions.
4. Severity guidance (locked):
   - BLOCKER: wrong results, security hole, breaking change, data loss
   - MAJOR: should fix before merge (anti-pattern, missing guard)
   - MINOR: fix if easy, else follow-up
   - NIT: optional polish
5. Be evidence-based — quote the exact offending lines in `quote`.
6. Quantify the consequence in `why` whenever possible (`8h job → 8 days`,
   `1k row table grows to 1M` etc.). Avoid vague language like
   "this is bad" or "could be improved".
"""


def _render_standards_block(standards: Sequence[Standard]) -> str:
    """Inline the authoritative reference catalog into the system prompt."""
    if not standards:
        return ""
    lines = ["## Authoritative references for this skill",
             "Cite at least one of these in every finding's `references` array."]
    for s in standards:
        lines.append(f"- **{s.label}** — {s.url}")
    return "\n".join(lines) + "\n"


async def call_with_findings(
    *,
    model: DatabricksClaude | None,
    system_prompt: str,
    user_prompt: str,
    skill_name: str,
    default_dimension: Dimension,
    standards: Sequence[Standard] = (),
    temperature: float = 0.15,
    max_tokens: int = 2400,
) -> tuple[list[Finding], dict[str, Any]]:
    """Single LLM call producing Finding[].

    `standards` are inlined into the system prompt so the model has the
    full catalog available without us doing post-hoc citation matching.

    Raises ModelError if the model is unreachable. Caller catches and
    falls back to deterministic logic.
    """
    if model is None:
        raise ModelError("No model adapter provided")
    full_system = (
        system_prompt
        + "\n\n" + _render_standards_block(standards)
        + "\n" + _FINDING_SCHEMA_INSTRUCTION
    )
    resp = await model.complete(
        system=full_system,
        user=user_prompt,
        config=ModelCallConfig(temperature=temperature, max_tokens=max_tokens, json_mode=True),
    )
    findings: list[Finding] = []
    if resp.parsed_json and "findings" in resp.parsed_json:
        for raw in resp.parsed_json["findings"]:
            try:
                sev = _coerce_severity(raw.get("severity"))
                dim = _coerce_dimension(raw.get("dimension"), default_dimension)
                refs = raw.get("references") or []
                # If the model returns short standard IDs ("CWE-89"), expand to label+url
                refs = _hydrate_references(refs, standards)
                findings.append(Finding(
                    rule_id=str(raw.get("rule_id", f"{skill_name}.uncategorized")),
                    skill=skill_name,
                    dimension=dim,
                    severity=sev,
                    confidence=int(raw.get("confidence", 60)),
                    file=str(raw.get("file", "unknown")),
                    line_start=int(raw.get("line_start", raw.get("line", 0))),
                    line_end=int(raw.get("line_end", raw.get("line", 0))),
                    title=str(raw.get("title", ""))[:200],
                    quote=raw.get("quote"),
                    why=str(raw.get("why", "")),
                    fix=raw.get("fix"),
                    references=refs,
                ))
            except (ValueError, TypeError) as exc:
                logger.warning("skill.parse_skip", skill=skill_name, error=str(exc)[:200])
    telemetry = {
        "model_calls": 1,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "estimated_cost_usd": resp.estimated_cost_usd,
    }
    return findings, telemetry


def _hydrate_references(refs: list[Any], standards: Sequence[Standard]) -> list[str]:
    """If the model returned just IDs (CWE-89), turn them into 'Label — URL' strings."""
    by_id = {s.id: s for s in standards}
    out: list[str] = []
    for r in refs:
        if not r:
            continue
        rs = str(r).strip()
        # Already a full reference (has a URL)
        if "—" in rs or "http" in rs:
            out.append(rs)
            continue
        # Maybe an ID we can hydrate
        std = by_id.get(rs)
        if std:
            out.append(f"{std.label} — {std.url}")
        else:
            out.append(rs)
    return out


async def call_with_text(
    *,
    model: DatabricksClaude | None,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.25,
    max_tokens: int = 1000,
) -> tuple[str, dict[str, Any]]:
    """Plain-text LLM call · used by skills that produce narrative."""
    if model is None:
        raise ModelError("No model adapter provided")
    resp = await model.complete(
        system=system_prompt, user=user_prompt,
        config=ModelCallConfig(temperature=temperature, max_tokens=max_tokens, json_mode=False),
    )
    return (resp.content or "").strip(), {
        "model_calls": 1,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "estimated_cost_usd": resp.estimated_cost_usd,
    }


def _coerce_severity(raw: Any) -> Severity:
    s = str(raw or "MAJOR").upper()
    return Severity(s) if s in {sev.value for sev in Severity} else Severity.MINOR


def _coerce_dimension(raw: Any, default: Dimension) -> Dimension:
    d = str(raw or default.value).lower()
    return Dimension(d) if d in {dim.value for dim in Dimension} else default


def apply_memory_adjustments(findings: list[Finding], ctx: SkillContext) -> list[Finding]:
    """Tune confidence per repo memory."""
    adj = (ctx.memory or {}).get("confidence_adjustments") or {}
    if not adj:
        return findings
    out: list[Finding] = []
    for f in findings:
        delta = float(adj.get(f.rule_id, 0))
        if delta:
            new_conf = max(0, min(100, int(f.confidence + delta)))
            f = f.model_copy(update={"confidence": new_conf})
        out.append(f)
    return out


def make_finding(
    *, rule_id: str, skill: str, dimension: Dimension, severity: Severity,
    confidence: int, file: str, line: int, title: str, why: str, fix: str | None,
    quote: str | None = None,
    references: list[str] | Sequence[Standard] | None = None,
) -> Finding:
    """Construct a Finding with optional structured references.

    `references` accepts:
      · list[str]            — pre-formatted reference strings (passed through)
      · list[Standard]       — Standard objects (converted to 'Label — URL')
      · None                 — empty list
    """
    refs: list[str]
    if references is None:
        refs = []
    elif references and isinstance(references[0], Standard):
        refs = [f"{s.label} — {s.url}" for s in references]   # type: ignore[union-attr]
    else:
        refs = list(references)  # type: ignore[arg-type]
    return Finding(
        rule_id=rule_id, skill=skill, dimension=dimension,
        severity=severity, confidence=confidence,
        file=file, line_start=line, line_end=line,
        title=title, why=why, fix=fix, quote=quote,
        references=refs,
    )
