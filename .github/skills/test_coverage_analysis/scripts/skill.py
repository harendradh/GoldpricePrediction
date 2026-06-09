"""Test Coverage Analysis skill · missing tests · weak assertions · test smells.

Purpose
-------
Identifies the gap between "code shipped" and "code validated." Catches
public functions added without tests, weak assertions that prove nothing,
and brittle test patterns (timing-dependent, order-dependent).

Methodology
-----------
1. **Deterministic structural pass** — scans the diff for:
   - Non-test source files with substantial additions (>30 lines)
   - No sibling test file in the same PR
   - Test-file additions with weak assertions (assertNotNull only)
2. **LLM contextual pass** — surfaces issues that need semantic reading:
   - New public function lacks any assertion covering its core behavior
   - Edge cases (boundary, error path) untested
   - Timing/order-dependent tests
   - Tests asserting implementation details vs observable behavior

Confidence is moderate (70–82) because "missing tests" is context-dependent
— some PRs are pure refactors, some change behavior. The LLM gets the diff
plus an instruction to skip refactor-only changes.

Authoritative standards consulted
---------------------------------
- Test Pyramid (Mike Cohn / Martin Fowler) https://martinfowler.com/bliki/TestPyramid.html
- F.I.R.S.T. principles (Robert Martin)    https://github.com/ghsukumar/SFDC_Best_Practices/wiki/F.I.R.S.T-Principles-of-Unit-Testing
- AAA pattern (Arrange-Act-Assert)         http://wiki.c2.com/?ArrangeActAssert
- Test Smells catalog                      https://testsmells.org/
- pytest Good Practices                    https://docs.pytest.org/en/stable/explanation/goodpractices.html
- Effective Java Item 77 (Don't ignore exceptions)

What this skill catches
-----------------------
- New public function added without any test in the same PR
- Test assertion that only checks non-null / non-empty (no semantic check)
- Tests with sleep() or time.sleep() (flakiness signal)
- Tests asserting on Map/Set iteration order (order-dependent flakiness)
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import Dimension, Severity, SkillContext, SkillResult
from skills._shared.llm_helper import apply_memory_adjustments, call_with_findings, make_finding
from skills._shared.patterns import TEST_PATTERNS
from skills._shared.standards import (
    AAA_PATTERN,
    CLEAN_CODE,
    EFFECTIVE_JAVA_77,
    FIRST_TEST_PRINCIPLES,
    PYTEST_GOOD_PRACTICES,
    TEST_PYRAMID,
    TEST_SMELLS,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)


@register_skill
class TestCoverageAnalysisSkill(Skill):
    name = "test_coverage_analysis"
    description = "Coverage gaps · weak assertions · test smells · Test-Pyramid grounded"
    dimensions = [Dimension.TESTING.value]

    STANDARDS = [
        TEST_PYRAMID, FIRST_TEST_PRINCIPLES, AAA_PATTERN, TEST_SMELLS,
        PYTEST_GOOD_PRACTICES, EFFECTIVE_JAVA_77, CLEAN_CODE,
    ]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        det = self._deterministic(ctx)
        llm: list = []
        telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
        fallback = True
        try:
            sys_p = (
                "You are a senior SDET. Your beat: net-new public "
                "functions / classes shipped without tests, modified business "
                "logic without updated tests, weak assertions (assertNotNull "
                "with no semantic check), missing edge cases (boundary + error "
                "paths), brittle tests (timing- or order-dependent).\n\n"
                "Skip pure refactors (no behavior change). Cite the Test Pyramid, "
                "F.I.R.S.T principles, or the Test Smells catalog in every finding."
            )
            llm, telemetry = await call_with_findings(
                model=model, system_prompt=sys_p,
                user_prompt=f"Test coverage review.\n\nDiff:\n```\n{self.diff_blob(ctx, 5000)}\n```",
                skill_name=self.name, default_dimension=Dimension.TESTING,
                standards=self.STANDARDS,
            )
            fallback = False
        except ModelError as exc:
            logger.warning("skill.test_coverage.fallback", error=str(exc)[:200])
        merged = apply_memory_adjustments(self._dedupe(det + llm), ctx)
        for f in merged:
            f.auto_postable = f.confidence >= 75
        return SkillResult(findings=merged, fallback_used=fallback, **telemetry)

    def _deterministic(self, ctx: SkillContext) -> list:
        """Structural checks on test / non-test additions in the PR."""
        if ctx.pr is None:
            return []
        out = []
        added_paths = {f.path for f in ctx.pr.files if not f.is_test_file and not f.is_generated}
        test_paths = {f.path for f in ctx.pr.files if f.is_test_file}

        # Net-new code without sibling test file
        for src in added_paths:
            if any(src.replace(".py", "") in tp for tp in test_paths):
                continue
            src_fc = next((f for f in ctx.pr.files if f.path == src), None)
            if src_fc and src_fc.additions > 30 and src_fc.deletions < 5:
                out.append(make_finding(
                    rule_id="test.no_sibling_test", skill=self.name,
                    dimension=Dimension.TESTING, severity=Severity.MAJOR,
                    confidence=72, file=src, line=0,
                    title=f"Net-new code in {src} without a sibling test file in this PR",
                    why=("Untested logic enters main; first feedback comes only when production breaks. "
                         "Per the Test Pyramid, unit tests are the cheapest validation layer."),
                    fix="Add tests for the happy path + one error path before merging.",
                    references=[TEST_PYRAMID, FIRST_TEST_PRINCIPLES, AAA_PATTERN],
                ))

        # Weak-assertion patterns inside test files
        for fc in ctx.pr.files:
            if not fc.is_test_file:
                continue
            for hunk in fc.hunks:
                start = hunk.get("new_start", 1)
                for off, line in enumerate(hunk.get("lines", [])):
                    for spec in TEST_PATTERNS:
                        if spec.regex.search(line):
                            out.append(make_finding(
                                rule_id=spec.rule_id, skill=self.name,
                                dimension=spec.dimension, severity=spec.severity,
                                confidence=80, file=fc.path, line=start + off,
                                title=spec.title, why=spec.why, fix=spec.fix,
                                quote=line.lstrip("+").strip()[:200],
                                references=spec.references,
                            ))
        return out

    @staticmethod
    def _dedupe(findings):
        seen = set()
        out = []
        for f in findings:
            k = (f.rule_id, f.file, f.line_start)
            if k not in seen:
                seen.add(k)
                out.append(f)
        return out
