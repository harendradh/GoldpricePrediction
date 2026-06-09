"""Architecture Validation skill · layer integrity · public API · DI · module cohesion.

Purpose
-------
Catches architectural drift before it ossifies. Operates against a locked
layer order (`ui → api → domain → infra → core`) and flags imports that
violate the dependency direction, public-API changes that break consumers,
and module-cohesion smells (god classes, parameter explosion).

Methodology
-----------
1. **Deterministic import analysis** — parses `from X import Y` / `import X`
   in added diff lines, maps each side to a layer, flags violations
   (lower layer importing from higher layer).
2. **LLM contextual pass** — surfaces issues that need understanding of
   how the classes are wired together: god classes, IoC violations,
   framework leak into domain, missing abstraction boundary.

Authoritative standards consulted
---------------------------------
- Clean Architecture (Uncle Bob)                 https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Domain-Driven Design (Eric Evans)              https://www.domainlanguage.com/ddd/
- SOLID principles                               https://en.wikipedia.org/wiki/SOLID
- Microservices Patterns (Richardson)            https://microservices.io/patterns/
- Refactoring (Fowler) — Code Smells             https://martinfowler.com/refactoring/
- 12-Factor App                                  https://12factor.net/

What this skill catches
-----------------------
- `from infra import …` inside a `core/` or `domain/` module → layer violation
- Public method renamed / removed without `@Deprecated` warm-up window
- Framework imports (`flask`, `django`, `spring`) inside `domain/`
- God classes (>15 public methods or >800-line files)
- Functions with 6+ parameters (constructor / param-object smell)

What this skill explicitly does NOT catch
-----------------------------------------
- Performance of those layers → `performance_analysis`
- Security of public APIs → `security_scan`
- Test coverage of public APIs → `test_coverage_analysis`
"""
from __future__ import annotations

import re

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, Severity, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.standards import (
    CLEAN_ARCHITECTURE,
    CLEAN_CODE,
    DDD_EVANS,
    FOWLER_REFACTORING,
    MICROSERVICE_PATTERNS,
    SOLID_PRINCIPLES,
    TWELVE_FACTOR_APP,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)

# Layer order: top depends on bottom. Violations are imports pointing UP.
_LAYERS = [
    ("ui",       ("/ui/", "/components/", "/pages/", "/frontend/", "/views/")),
    ("api",      ("/api/", "/controllers/", "/routes/", "/endpoints/")),
    ("domain",   ("/domain/", "/services/", "/usecases/", "/biz/")),
    ("infra",    ("/db/", "/persistence/", "/repositories/", "/storage/", "/queue/", "/cache/")),
    ("core",     ("/core/", "/lib/", "/utils/", "/shared/")),
]
_IMPORT_RE = re.compile(r"^\+\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))")


@register_skill
class ArchitectureValidationSkill(Skill):
    name = "architecture_validation"
    description = "Layer integrity · public API · DI patterns · module cohesion · Clean Architecture grounded"
    dimensions = [Dimension.ARCHITECTURE.value]

    STANDARDS = [
        CLEAN_ARCHITECTURE, DDD_EVANS, SOLID_PRINCIPLES,
        MICROSERVICE_PATTERNS, FOWLER_REFACTORING, CLEAN_CODE, TWELVE_FACTOR_APP,
    ]

    def should_run(self, ctx: SkillContext) -> bool:
        if ctx.pr is None:
            return False
        signals = self._signals(ctx)
        return bool(signals)

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._layer_violation_pass(ctx)
        llm = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You are a staff engineer reviewing architectural compliance "
                "against Clean Architecture and DDD principles. Your beat: "
                "layer violations (importing from a higher layer), public API "
                "changes without deprecation, IoC violations (concrete impls "
                "in constructors), framework leaks into domain code, god "
                "classes, and breaking schema changes. Skip security/perf/"
                "style (delegated). Cite Clean Architecture rules, SOLID "
                "principles, or the relevant Refactoring code-smell in every finding."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"Architecture review.\n\nSignals: {self._signals(ctx)}\n\nDiff:\n```\n{self.diff_blob(ctx, 5000)}\n```",
                skill_name=self.name, default_dimension=Dimension.ARCHITECTURE,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.architecture.fallback", error=str(exc)[:200])
        merged = apply_memory_adjustments(self._dedupe(det + llm), ctx)
        for f in merged:
            f.auto_postable = f.confidence >= 75
        return SkillResult(findings=merged, fallback_used=fallback, **telemetry,
                           payload={"deterministic": len(det), "llm": len(llm)})

    @staticmethod
    def _signals(ctx: SkillContext) -> list[str]:
        if ctx.pr is None:
            return []
        sigs = []
        paths = " ".join(f.path for f in ctx.pr.files)
        if any(p in paths for p in ("/api/", "/controllers/", "openapi")):
            sigs.append("public_api")
        if any(p in paths for p in ("/db/models", "migration", "alembic")):
            sigs.append("data_model_change")
        if (ctx.pr.total_additions + ctx.pr.total_deletions) > 500:
            sigs.append("large_change")
        return sigs

    def _layer_violation_pass(self, ctx: SkillContext) -> list:
        if ctx.pr is None:
            return []
        out = []
        for fc in ctx.pr.files:
            if fc.language not in {"python", "java", "scala", "typescript"}:
                continue
            file_layer = self._layer_of(fc.path)
            if file_layer is None:
                continue
            file_idx = next(i for i, (n, _) in enumerate(_LAYERS) if n == file_layer)
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                for off, line in enumerate(hunk.get("lines", [])):
                    m = _IMPORT_RE.match(line)
                    if not m:
                        continue
                    target = m.group(1) or m.group(2) or ""
                    target_layer = self._layer_of_module(target)
                    if target_layer is None:
                        continue
                    target_idx = next(i for i, (n, _) in enumerate(_LAYERS) if n == target_layer)
                    if target_idx < file_idx:
                        out.append(make_finding(
                            rule_id="arch.layer_violation", skill=self.name,
                            dimension=Dimension.ARCHITECTURE, severity=Severity.MAJOR,
                            confidence=80, file=fc.path, line=start + off,
                            title=f"Layer violation · {file_layer} → {target_layer}",
                            quote=line.lstrip("+").strip()[:200],
                            why=(f"`{file_layer}` should not depend on `{target_layer}` per locked layer order. "
                                 "Breaks dependency inversion."),
                            fix=(f"Define an interface in `{file_layer}` and inject the "
                                 f"`{target_layer}` impl at composition root (Dependency Inversion Principle)."),
                            references=[CLEAN_ARCHITECTURE, SOLID_PRINCIPLES],
                        ))
        return out

    @staticmethod
    def _layer_of(path: str) -> str | None:
        for layer, hints in _LAYERS:
            if any(h in path for h in hints):
                return layer
        return None

    @staticmethod
    def _layer_of_module(module: str) -> str | None:
        norm = "/" + module.replace(".", "/") + "/"
        for layer, hints in _LAYERS:
            if any(h in norm for h in hints):
                return layer
        return None

    @staticmethod
    def _dedupe(findings):
        seen = set(); out = []
        for f in findings:
            k = (f.rule_id, f.file, f.line_start)
            if k not in seen:
                seen.add(k); out.append(f)
        return out
