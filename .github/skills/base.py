"""Skill abstract base + global registry.

Skills are pure Python classes with structured I/O. The host (an agent or
a workflow) provides a SkillContext and gets back a SkillResult.
"""
from __future__ import annotations

import abc
import time
from typing import Any, ClassVar

from Agents.Core.model import DatabricksClaude
from Agents.Core.observability import get_logger, trace_span
from Agents.Core.schemas import Finding, SkillContext, SkillResult

logger = get_logger(__name__)


class Skill(abc.ABC):
    """Abstract skill · subclass + decorate with @register_skill."""
    name: ClassVar[str]
    description: ClassVar[str]
    dimensions: ClassVar[list[str]]

    def should_run(self, ctx: SkillContext) -> bool:
        if ctx.pr is None:
            return True
        return not ctx.pr.smart_skip_eligible

    @abc.abstractmethod
    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        ...

    async def execute(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        """Public entry · wraps run() with timing + error capture."""
        t0 = time.perf_counter()
        try:
            with trace_span(f"skill.{self.name}"):
                if not self.should_run(ctx):
                    return SkillResult(duration_ms=0)
                result = await self.run(ctx, model=model)
        except Exception as exc:
            logger.exception("skill.execute.failed", skill=self.name)
            return SkillResult(
                fallback_used=True,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                payload={"error": f"{type(exc).__name__}: {exc}"},
            )
        result.duration_ms = int((time.perf_counter() - t0) * 1000)
        return result

    # Convenience for subclasses that need a diff blob to inject in prompts
    def diff_blob(self, ctx: SkillContext, max_chars: int = 4000) -> str:
        if ctx.pr is None or not ctx.pr.files:
            return ""
        parts: list[str] = []
        budget = max_chars
        for f in ctx.pr.files:
            if budget <= 0:
                break
            header = f"\n### {f.path}  ({f.language}, +{f.additions}/-{f.deletions})\n"
            parts.append(header)
            budget -= len(header)
            for h in f.hunks:
                chunk = "\n".join(h.get("lines", [])) + "\n"
                if len(chunk) > budget:
                    parts.append(chunk[:budget] + "\n…\n")
                    budget = 0
                    break
                parts.append(chunk)
                budget -= len(chunk)
        return "".join(parts)


class _Registry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def names(self) -> list[str]:
        return sorted(self._skills.keys())


_REGISTRY = _Registry()


def get_skill_registry() -> _Registry:
    return _REGISTRY


def register_skill(cls: type[Skill]) -> type[Skill]:
    _REGISTRY.register(cls())
    return cls
