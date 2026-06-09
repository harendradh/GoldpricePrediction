"""CAB Document SubAgent · assembles the 8-section change brief."""
from __future__ import annotations

from typing import Any

from Agents.Core.model import DatabricksClaude
from Agents.Core.observability import get_logger
from Agents.Core.schemas import CABBrief, CABBriefSection, CABRiskLevel, SkillContext
from skills.base import get_skill_registry
from Agents.SubAgents.base import SubAgent, SubAgentResult

logger = get_logger(__name__)


class CABDocumentAgent(SubAgent):
    name = "cab_document_agent"
    description = "Generates 8-section ServiceNow Standard Change brief"

    SECTIONS = [
        "change_summary", "business_impact", "risk_assessment",
        "rollback_plan", "deployment_plan", "dependencies",
        "validation_steps", "implementation_details",
    ]

    def skills(self) -> list[str]:
        return ["cab_section_generation", "risk_assessment"]

    async def run(self, ctx: SkillContext, model: DatabricksClaude | None) -> SubAgentResult:
        registry = get_skill_registry()
        risk_skill = registry.get("risk_assessment")
        cab_skill = registry.get("cab_section_generation")
        findings = ctx.parameters.get("findings", [])
        findings_summary = self._findings_summary(findings)

        # 1. Compute risk level
        risk_ctx = SkillContext(pr=ctx.pr, memory=ctx.memory,
                                parameters={"findings": findings})
        risk_result = await risk_skill.execute(risk_ctx, model)
        risk_level_str = (risk_result.payload or {}).get("risk_level", "low").upper()

        # 2. Generate each LLM-narrated section
        sections: list[dict[str, Any]] = []
        total_mc = total_it = total_ot = 0
        total_cost = 0.0
        fallback_seen = False
        for section_id in ("change_summary", "business_impact", "risk_assessment",
                           "deployment_plan", "validation_steps", "implementation_details"):
            section_ctx = SkillContext(
                pr=ctx.pr, memory=ctx.memory,
                parameters={"section_id": section_id, "risk_level": risk_level_str,
                            "findings_summary": findings_summary},
            )
            r = await cab_skill.execute(section_ctx, model)
            section_payload = (r.payload or {}).get("section")
            if section_payload:
                sections.append(section_payload)
            total_mc += r.model_calls; total_it += r.input_tokens
            total_ot += r.output_tokens; total_cost += r.estimated_cost_usd
            fallback_seen = fallback_seen or r.fallback_used

        # 3. Deterministic sections (rollback + dependencies)
        sections.append(self._rollback(ctx.pr))
        sections.append(self._dependencies(ctx.pr))

        # 4. Sort sections per fixed order
        order = {s: i for i, s in enumerate(self.SECTIONS)}
        sections.sort(key=lambda s: order.get(s["section_id"], 99))

        # 5. Assemble final markdown
        brief = self._assemble(ctx.pr, sections, CABRiskLevel(risk_level_str.lower()))

        return SubAgentResult(
            agent_name=self.name,
            success=True,
            duration_ms=0,
            payload={"brief": brief.model_dump(mode="json"),
                     "risk_level": risk_level_str.lower(),
                     "risk_score": (risk_result.payload or {}).get("risk_score", 0)},
            skills_invoked=["risk_assessment", "cab_section_generation"],
            model_calls=total_mc, input_tokens=total_it, output_tokens=total_ot,
            estimated_cost_usd=round(total_cost, 6),
            fallback_used=fallback_seen,
        )

    @staticmethod
    def _findings_summary(findings) -> str:
        if not findings:
            return "no findings"
        by_sev: dict[str, int] = {}
        for f in findings:
            sev = (f.severity.value if hasattr(f, "severity")
                   else str(f.get("severity", "MINOR")).upper())
            by_sev[sev] = by_sev.get(sev, 0) + 1
        return ", ".join(f"{k}: {v}" for k, v in by_sev.items())

    @staticmethod
    def _rollback(pr) -> dict[str, Any]:
        return {
            "section_id": "rollback_plan",
            "title": "Rollback Plan",
            "body_markdown": (
                f"1. `git revert <commit-sha>` on `{pr.base_branch if pr else 'main'}`.\n"
                "2. Wait for CI on the revert commit.\n"
                "3. If schema migrations were applied, run inverse migration first.\n"
                f"4. Notify owning team on-call channel; reference PR #{pr.pr_number if pr else 0}.\n"
                "5. Validate via service smoke-test suite.\n"
                "6. Update change ticket with rollback timestamp + actor."
            ),
            "is_llm_generated": False,
            "confidence": 95,
        }

    @staticmethod
    def _dependencies(pr) -> dict[str, Any]:
        touched: set[str] = set()
        if pr:
            for f in pr.files:
                p = f.path.lower()
                if "kafka" in p or "consumer" in p:
                    touched.add("Kafka topics + downstream consumers")
                if "snowflake" in p or "delta" in p:
                    touched.add("Snowflake / Delta tables")
                if "/api/" in p:
                    touched.add("REST API consumers")
                if "schema" in p or "migration" in p:
                    touched.add("Database schema (downstream readers)")
        body = ("\n".join(f"- {s}" for s in sorted(touched))
                if touched else "_(no inferred external dependencies — verify with owning team)_")
        return {
            "section_id": "dependencies",
            "title": "Dependencies",
            "body_markdown": body,
            "is_llm_generated": False,
            "confidence": 70,
        }

    @staticmethod
    def _assemble(pr, sections: list[dict[str, Any]], risk: CABRiskLevel) -> CABBrief:
        header = (
            f"# Change Brief · PR #{pr.pr_number if pr else 0} · `{pr.repo if pr else ''}`\n\n"
            "| | |\n|---|---|\n"
            f"| **Title** | {pr.title if pr else ''} |\n"
            f"| **Author** | {pr.author if pr else ''} |\n"
            f"| **Branch** | `{pr.branch if pr else ''}` → `{pr.base_branch if pr else 'main'}` |\n"
            f"| **Files changed** | {pr.files_changed if pr else 0} (+"
            f"{pr.total_additions if pr else 0}/-{pr.total_deletions if pr else 0}) |\n"
            f"| **Risk classification** | **{risk.value.upper()}** |\n\n---\n"
        )
        body_parts = [header]
        for s in sections:
            body_parts.append(f"\n## {s['title']}\n\n{s['body_markdown']}\n")
        body_parts.append("\n---\n*Generated by ChangePilot · paste into ServiceNow as Standard Change*\n")
        return CABBrief(
            pr_id=pr.pr_id if pr else 0,
            repo=pr.repo if pr else "",
            pr_number=pr.pr_number if pr else 0,
            title=pr.title if pr else "",
            risk_level=risk,
            sections=[CABBriefSection(**s) for s in sections],
            full_markdown="".join(body_parts),
        )
