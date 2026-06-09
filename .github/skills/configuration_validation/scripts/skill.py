"""Configuration Validation skill · CORS · SSL · debug flags · env var hygiene.

Purpose
-------
Catches the small configuration mistakes that translate into large security
incidents: wildcard CORS with credentials, disabled TLS verification, debug
mode hardcoded, secrets committed in `application.yml` / `appsettings.json`.

The 12-Factor App methodology and OWASP A05 (Security Misconfiguration) are
the spine of this skill.

Methodology
-----------
1. **Deterministic regex pass** — high-precision matches on CORS / SSL /
   debug-flag patterns, sourced from OWASP Cheat Sheets and 12-Factor.
2. **LLM contextual pass** — catches issues where the misconfiguration is
   only visible when reading multiple config files together (e.g. dev
   config promoted to prod, secret fields not externalized).

Authoritative standards consulted
---------------------------------
- 12-Factor App                              https://12factor.net/
- OWASP A05 — Security Misconfiguration      https://owasp.org/Top10/A05_2021-Security_Misconfiguration/
- OWASP Secure Headers Project               https://owasp.org/www-project-secure-headers/
- CWE-295 (Cert validation)                  https://cwe.mitre.org/data/definitions/295.html
- CWE-489 (Leftover debug code)              https://cwe.mitre.org/data/definitions/489.html

What this skill catches
-----------------------
- CORS `*` origin with `allow_credentials=True` → token leak vector
- `verify=False` in HTTP clients → TLS bypass
- `DEBUG = True` hardcoded → stack trace + env leakage in prod
- Secrets in committed YAML / JSON config files
- Cookie flags missing (HttpOnly / Secure / SameSite)

What this skill explicitly does NOT catch
-----------------------------------------
- Code-level secret literals (delegated to `security_scan`)
- Database / migration config (delegated to `database_migration`)
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import CONFIG_PATTERNS
from skills._shared.standards import (
    CWE_295_CERT_VALIDATION,
    CWE_489_DEBUG_FEATURES,
    OWASP_A05_SECURITY_MISCONFIG,
    TWELVE_FACTOR_APP,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)


@register_skill
class ConfigurationValidationSkill(Skill):
    name = "configuration_validation"
    description = "Config sanity · CORS · SSL · debug flags · 12-Factor App grounded"
    dimensions = [Dimension.CONFIGURATION.value, Dimension.SECURITY.value]

    STANDARDS = [
        TWELVE_FACTOR_APP, OWASP_A05_SECURITY_MISCONFIG,
        CWE_295_CERT_VALIDATION, CWE_489_DEBUG_FEATURES,
    ]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm: list = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You review configuration changes against the 12-Factor App "
                "methodology and OWASP A05 (Security Misconfiguration). Your beat: "
                "wildcard CORS with credentials, SSL verification disabled, debug "
                "flags hardcoded true, missing env-var defaults that crash in non-dev, "
                "secrets in `application.yml` / `appsettings.json`, missing cookie "
                "flags (HttpOnly / Secure / SameSite). Cite 12-Factor principles "
                "and OWASP A05 in every finding."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"Configuration review.\n\nDiff:\n```\n{self.diff_blob(ctx, 4500)}\n```",
                skill_name=self.name, default_dimension=Dimension.CONFIGURATION,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.config.fallback", error=str(exc)[:200])
        merged = apply_memory_adjustments(det + llm, ctx)
        for f in merged:
            f.auto_postable = f.confidence >= 78
        return SkillResult(findings=merged, fallback_used=fallback, **telemetry)

    def _deterministic(self, ctx: SkillContext) -> list:
        """Pattern-based catches drawn from OWASP secure-config cheat sheets."""
        if ctx.pr is None:
            return []
        out = []
        for fc in ctx.pr.files:
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                hunk_text = "\n".join(hunk.get("lines", []))
                for spec in CONFIG_PATTERNS:
                    if spec.regex.search(hunk_text):
                        loc = start
                        quote = hunk_text[:120]
                        for off, ln in enumerate(hunk.get("lines", [])):
                            if spec.regex.search(ln):
                                loc = start + off
                                quote = ln.lstrip("+").strip()
                                break
                        out.append(make_finding(
                            rule_id=spec.rule_id, skill=self.name,
                            dimension=spec.dimension, severity=spec.severity,
                            confidence=88, file=fc.path, line=loc,
                            title=spec.title, why=spec.why, fix=spec.fix,
                            quote=quote[:200],
                            references=spec.references,
                        ))
        return out
