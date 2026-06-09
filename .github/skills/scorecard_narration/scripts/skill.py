"""Scorecard Narration skill · 2-paragraph LLM analysis of team metrics.

Purpose
-------
Turns a team's DORA + SPACE metrics into two paragraphs of narrative the
eng lead actually reads (vs. a wall of numbers in a dashboard).

Authoritative standards consulted
---------------------------------
- DORA Four Key Metrics (Accelerate · Forsgren, Humble, Kim)
- SPACE Framework (Forsgren et al, ACM Queue 2021)
- Google SRE Book — Eliminating Toil, On-Call Rotations
"""
from __future__ import annotations

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import ScorecardMetrics, SkillContext, SkillResult
from skills._shared.llm_helper import call_with_text
from skills._shared.standards import DORA_METRICS, GOOGLE_SRE_BOOK, SPACE_FRAMEWORK
from skills.base import Skill, register_skill

logger = get_logger(__name__)


@register_skill
class ScorecardNarrationSkill(Skill):
    name = "scorecard_narration"
    description = "Narrates team scorecard metrics into 2-paragraph analysis · DORA / SPACE grounded"
    dimensions = ["intelligence"]

    STANDARDS = [DORA_METRICS, SPACE_FRAMEWORK, GOOGLE_SRE_BOOK]

    def should_run(self, ctx: SkillContext) -> bool:
        return ctx.parameters.get("metrics") is not None

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        metrics_raw = ctx.parameters["metrics"]
        metrics = ScorecardMetrics(**metrics_raw) if not isinstance(metrics_raw, ScorecardMetrics) else metrics_raw

        signals = self._risk_signals(metrics)
        grade = self._grade(metrics)

        try:
            sys_p = (
                "You are a senior engineering manager interpreting team health metrics. "
                "Write a 2-paragraph analysis (≤150 words). Paragraph 1: state the grade "
                "and lead with the headline metric. Paragraph 2: pick the most actionable "
                "signal and explain it. Be honest. Don't sugar-coat red zones. Cite numbers, "
                "not adjectives."
            )
            usr_p = (
                f"Team: {metrics.team_label}\nWindow: {metrics.window_days} days\nGrade: {grade}\n"
                f"Total PRs: {metrics.total_prs}\nFindings: {metrics.findings_total} "
                f"({metrics.findings_per_pr}/PR)\nBlocker leakage: {metrics.blocker_leakage_rate*100:.1f}%\n"
                f"Dismissal: {metrics.dismissal_rate*100:.0f}%\n"
                f"Median cycle time: {metrics.median_cycle_time_hours}h\n"
                f"Risk signals: {'; '.join(signals) or '(none)'}"
            )
            narrative, telemetry = await call_with_text(
                model=model, system_prompt=sys_p, user_prompt=usr_p,
                temperature=0.3, max_tokens=500,
            )
            llm_ok = True
        except ModelError as exc:
            logger.warning("skill.scorecard.fallback", error=str(exc)[:200])
            narrative = self._deterministic_narrative(metrics, grade, signals)
            telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
            llm_ok = False

        return SkillResult(
            payload={
                "narrative_markdown": narrative,
                "grade": grade,
                "risk_signals": signals,
                "recommended_actions": self._actions(metrics, signals),
            },
            fallback_used=not llm_ok,
            **telemetry,
        )

    @staticmethod
    def _risk_signals(m: ScorecardMetrics) -> list[str]:
        sigs = []
        if m.blocker_leakage_rate > 0.10:
            sigs.append(f"blocker_leakage_high ({m.blocker_leakage_rate*100:.1f}%)")
        elif m.blocker_leakage_rate > 0.05:
            sigs.append(f"blocker_leakage_yellow ({m.blocker_leakage_rate*100:.1f}%)")
        if m.dismissal_rate > 0.50:
            sigs.append(f"dismissal_rate_high ({m.dismissal_rate*100:.0f}%)")
        if m.median_cycle_time_hours and m.median_cycle_time_hours > 48:
            sigs.append(f"cycle_time_high ({m.median_cycle_time_hours:.0f}h)")
        if m.queue_depth > 20:
            sigs.append(f"queue_backlog ({m.queue_depth})")
        return sigs

    @staticmethod
    def _grade(m: ScorecardMetrics) -> str:
        score = 100
        if m.blocker_leakage_rate > 0.10: score -= 30
        elif m.blocker_leakage_rate > 0.05: score -= 15
        if m.dismissal_rate > 0.50: score -= 10
        elif m.dismissal_rate > 0.35: score -= 5
        if m.median_cycle_time_hours and m.median_cycle_time_hours > 72: score -= 15
        elif m.median_cycle_time_hours and m.median_cycle_time_hours > 24: score -= 5
        if m.queue_depth > 30: score -= 10
        for cutoff, grade in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
            if score >= cutoff:
                return grade
        return "F"

    @staticmethod
    def _actions(m: ScorecardMetrics, sigs: list[str]) -> list[str]:
        actions = []
        if m.dismissal_rate > 0.50:
            actions.append("Audit the top 3 dismissed rules · tune or retire them.")
        if m.blocker_leakage_rate > 0.05:
            actions.append("Review every dismissed BLOCKER in the window for justification.")
        if m.queue_depth > 20:
            actions.append("Set a 'queue under 20' SLA and enforce via reminder bot.")
        if m.median_cycle_time_hours and m.median_cycle_time_hours > 48:
            actions.append("Find PRs sitting longest · usually 1-2 stragglers drive the median.")
        if not actions:
            actions.append("Health is good · sustain cadence, watch slope week-over-week.")
        return actions

    @staticmethod
    def _deterministic_narrative(m: ScorecardMetrics, grade: str, signals: list[str]) -> str:
        out = [
            f"**{m.team_label} · grade {grade} over last {m.window_days} days.** ",
            f"{m.total_prs} PR(s) producing {m.findings_total} finding(s) "
            f"({m.findings_per_pr:.1f}/PR). Blocker leakage {m.blocker_leakage_rate*100:.1f}%, "
            f"dismissal {m.dismissal_rate*100:.0f}%.",
        ]
        if signals:
            out.append("\n\n**Watch:**\n" + "\n".join(f"- {s}" for s in signals))
        return "".join(out)
