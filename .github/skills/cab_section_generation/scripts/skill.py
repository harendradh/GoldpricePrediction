"""CAB Section Generation skill · writes one section of a change brief.

Purpose
-------
Generates the prose body of one CAB-brief section (change_summary,
business_impact, risk_assessment, deployment_plan, validation_steps,
implementation_details) grounded in ITIL 4 Change Enablement guidance.

Methodology
-----------
1. Build a prompt scoped to the requested section_id.
2. Inline the authoritative ITIL 4 + DORA references so the model writes
   from a grounded vocabulary (not generic AI prose).
3. Fallback to a deterministic template if the model is unreachable —
   the CAB pipeline must produce *something* even offline.

Authoritative standards consulted
---------------------------------
- ITIL 4 · Change Enablement practice
- DORA Four Key Metrics (deployment frequency, lead time, MTTR, change failure rate)
- Google SRE Book · The Production Environment, Release Engineering
- NIST CSF 2.0 · Govern function
"""
from __future__ import annotations

from typing import Any

from Agents.Core.model import DatabricksClaude, ModelError
from Agents.Core.observability import get_logger
from Agents.Core.schemas import CABBriefSection, SkillContext, SkillResult
from skills._shared.llm_helper import call_with_text
from skills._shared.standards import (
    DORA_METRICS,
    GOOGLE_SRE_BOOK,
    ITIL_4_CHANGE_MGMT,
    NIST_CSF_2,
)
from skills.base import Skill, register_skill

logger = get_logger(__name__)


@register_skill
class CABSectionGenerationSkill(Skill):
    name = "cab_section_generation"
    description = "Writes one section of an enterprise CAB Standard Change brief · ITIL 4 / DORA grounded"
    dimensions = ["governance"]

    STANDARDS = [ITIL_4_CHANGE_MGMT, DORA_METRICS, GOOGLE_SRE_BOOK, NIST_CSF_2]

    SECTION_TITLES = {
        "change_summary": "Change Summary",
        "business_impact": "Business Impact",
        "risk_assessment": "Risk Assessment",
        "deployment_plan": "Deployment Plan",
        "validation_steps": "Validation Steps",
        "implementation_details": "Implementation Details",
    }

    def should_run(self, ctx: SkillContext) -> bool:
        return ctx.parameters.get("section_id") is not None

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None = None) -> SkillResult:
        section_id: str = ctx.parameters.get("section_id", "change_summary")
        risk_level: str = ctx.parameters.get("risk_level", "LOW")
        findings_summary: str = ctx.parameters.get("findings_summary", "no findings")

        try:
            sys_p = (
                "You write change-management briefs for a regulated engineering org. Your "
                "audience is a CAB board (mixed eng + risk + compliance). Be concise, "
                "specific, evidence-based. No marketing language. Active voice. Markdown only. "
                f"Section to write: `{section_id}` — produce only the BODY of this section "
                "(no title)."
            )
            usr_p = (
                f"Facts: PR #{ctx.pr.pr_number if ctx.pr else 0} '{ctx.pr.title if ctx.pr else ''}' "
                f"by {ctx.pr.author if ctx.pr else ''} in {ctx.pr.repo if ctx.pr else ''}.\n"
                f"Files: {ctx.pr.files_changed if ctx.pr else 0} (+{ctx.pr.total_additions if ctx.pr else 0}/"
                f"-{ctx.pr.total_deletions if ctx.pr else 0}).\n"
                f"Risk: {risk_level}.\nFindings: {findings_summary}.\n\n"
                f"Diff:\n```\n{self.diff_blob(ctx, 2200)}\n```\n\n"
                f"Write the `{section_id}` section body (markdown · no title header)."
            )
            body, telemetry = await call_with_text(
                model=model, system_prompt=sys_p, user_prompt=usr_p,
                temperature=0.3, max_tokens=700,
            )
            llm_ok = True
        except ModelError as exc:
            logger.warning("skill.cab_section.fallback", section=section_id, error=str(exc)[:200])
            body = self._deterministic_section(section_id, ctx, risk_level, findings_summary)
            telemetry = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
            llm_ok = False

        section = CABBriefSection(
            section_id=section_id,
            title=self.SECTION_TITLES.get(section_id, section_id.replace("_", " ").title()),
            body_markdown=body,
            is_llm_generated=llm_ok,
            confidence=85 if llm_ok else 55,
        )
        return SkillResult(
            payload={"section": section.model_dump(mode="json")},
            fallback_used=not llm_ok,
            **telemetry,
        )

    @staticmethod
    def _deterministic_section(section_id: str, ctx: SkillContext, risk: str, findings_summary: str) -> str:
        pr = ctx.pr
        templates = {
            "change_summary": (
                f"PR #{pr.pr_number if pr else 0} '{pr.title if pr else ''}' "
                f"modifies {pr.files_changed if pr else 0} file(s) "
                f"(+{pr.total_additions if pr else 0}/-{pr.total_deletions if pr else 0})."
            ),
            "business_impact": (
                "- Code path improvement\n- No customer-facing surface change\n"
                "_(LLM narration unavailable · refer to PR description.)_"
            ),
            "risk_assessment": (
                f"Risk classification: **{risk}**.\n\n{findings_summary}.\n\n"
                "Probability · medium · Impact · medium · Detectability · high "
                "(test suite + canary).\n_(Refine via LLM-narrated content when model is available.)_"
            ),
            "deployment_plan": (
                "1. Deploy to dev environment · run full test suite.\n"
                "2. Promote to staging · run integration tests.\n"
                "3. Promote to prod · within standard release window.\n"
                "4. Monitor SLO dashboards 1h post-deploy."
            ),
            "validation_steps": (
                "1. CI pipeline green.\n2. Manual smoke per service runbook.\n"
                "3. Spot-check observability metrics post-deploy.\n"
                "4. Verify rollback procedure once in non-prod."
            ),
            "implementation_details": (
                "_(LLM narration unavailable · refer to commit messages and diff.)_"
            ),
        }
        return templates.get(section_id, "_(no content)_")
