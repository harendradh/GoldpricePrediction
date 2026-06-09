# ChangePilot Studio · Copilot Instructions

> **Loaded automatically by GitHub Copilot Chat / Coding Agents.** This file
> is the canonical contract for how the ChangePilot agents are organized,
> how skills compose, and which files own which concern. Edit with care —
> the agent runtime references this document for orientation.

---

## 1 · What ChangePilot Studio is

A production-grade AI platform for **PR code review · CAB documentation ·
team scorecards**. It runs on top of **Google ADK + Databricks-hosted
Claude** (via LiteLLM), with explicit **Perception · Reasoning · Planning ·
Action** modules and a skill-driven (not prompt-only) architecture.

All agent logic lives in two places only:

| Path | Owns |
|---|---|
| `Agents/`           | The agent code: MasterAgent + SubAgents + Core |
| `.github/skills/`   | The 17 reusable skills the agents compose |

The `backend/` directory is a thin FastAPI shell that exposes REST routes
and delegates to `MasterAgent`. The `frontend/` directory is a React UI
that renders responses. Neither contains agent logic of its own.

---

## 2 · The 10 sub-agents

| Sub-agent | Path | Owns |
|---|---|---|
| `CodeReviewAgent`         | `Agents/SubAgents/CodeReviewAgent/`         | Idiom · maintainability · docstrings · test gaps |
| `SecurityReviewAgent`     | `Agents/SubAgents/SecurityReviewAgent/`     | Always-on · injection · secrets · crypto · deps · config |
| `PerformanceReviewAgent`  | `Agents/SubAgents/PerformanceReviewAgent/`  | Spark · O(n²) · I/O · concurrency · resources |
| `ArchitectureAgent`       | `Agents/SubAgents/ArchitectureAgent/`       | Layer integrity · public API contracts · DB migrations |
| `TestCoverageAgent`       | `Agents/SubAgents/TestCoverageAgent/`       | Standalone test-quality lens |
| `DependencyAuditAgent`    | `Agents/SubAgents/DependencyAuditAgent/`    | Supply chain · CVE · pin hygiene |
| `GovernanceAgent`         | `Agents/SubAgents/GovernanceAgent/`         | Naming · ownership · release rules |
| `CABDocumentAgent`        | `Agents/SubAgents/CABDocumentAgent/`        | 8-section ServiceNow Standard Change brief |
| `ScorecardAgent`          | `Agents/SubAgents/ScorecardAgent/`          | Per-team narrative + grade + risk signals |
| `ReleaseReadinessAgent`   | `Agents/SubAgents/ReleaseReadinessAgent/`   | READY / NOT_READY verdict + risk score |

The **MasterAgent** at `Agents/MasterAgent/` orchestrates these via
explicit Perception → Reasoning → Planning → Action modules.

---

## 3 · The 17 skills (`.github/skills/`)

| Skill | File |
|---|---|
| `code_quality`               | `.github/skills/code_quality.py` |
| `security_scan`              | `.github/skills/security_scan.py` |
| `performance_analysis`       | `.github/skills/performance_analysis.py` |
| `architecture_validation`    | `.github/skills/architecture_validation.py` |
| `test_coverage_analysis`     | `.github/skills/test_coverage_analysis.py` |
| `dependency_audit`           | `.github/skills/dependency_audit.py` |
| `configuration_validation`   | `.github/skills/configuration_validation.py` |
| `database_migration`         | `.github/skills/database_migration.py` |
| `api_contract_validation`    | `.github/skills/api_contract_validation.py` |
| `error_handling_review`      | `.github/skills/error_handling_review.py` |
| `concurrency_analysis`       | `.github/skills/concurrency_analysis.py` |
| `resource_management`        | `.github/skills/resource_management.py` |
| `documentation_quality`      | `.github/skills/documentation_quality.py` |
| `governance_compliance`      | `.github/skills/governance_compliance.py` |
| `cab_section_generation`     | `.github/skills/cab_section_generation.py` |
| `scorecard_narration`        | `.github/skills/scorecard_narration.py` |
| `risk_assessment`            | `.github/skills/risk_assessment.py` |

Skills are Python classes with structured I/O (Pydantic-typed `Finding`
objects), graceful LLM fallback to deterministic regex passes, and
self-registration via `@register_skill`. They expose a single
`async run(context, model)` method and are stateless.

Shared helpers live alongside:

- `.github/skills/base.py`          — `Skill` ABC + registry
- `.github/skills/_patterns.py`     — regex pattern library
- `.github/skills/_llm_helper.py`   — LLM call helpers + JSON parsing

---

## 4 · The Perception · Reasoning · Planning · Action pipeline

Every `MasterAgent.review_pr()` invocation walks these phases:

```
Inputs
  │
  ▼
PERCEPTION   `Agents/MasterAgent/perception.py`
             · parses diff → PRContext (FileChange[], languages, smart-skip eligibility)
  │
  ▼
RECALL       `Agents/Core/memory.py` → RepoMemorySnapshot
             · confidence adjustments per rule from past dismissals
  │
  ▼
REASONING    `Agents/MasterAgent/reasoning.py`
             · derives Signals from PRContext + memory
             · which dimensions matter, what risk indicators are present
  │
  ▼
PLANNING     `Agents/MasterAgent/planning.py`
             · maps Signals → ExecutionPlan (which SubAgents to invoke)
             · always-on: security + code_review
             · conditional: performance, architecture, governance, …
  │
  ▼
ACTION       `Agents/MasterAgent/action.py`
             · executes SubAgents with bounded parallelism (4 concurrent)
             · dedupes + ranks findings
             · computes verdict (BLOCK / IMPROVE / MERGE / SMART_SKIP)
  │
  ▼
REMEMBER     AgentRunRecord persisted · payload returned
```

---

## 5 · Severity policy (LOCKED · all agents honor)

| Severity | Meaning | Example |
|---|---|---|
| **BLOCKER** | Will produce wrong results, security holes, or breaking changes | mutable default arg, SQL injection, dropped column referenced downstream |
| **MAJOR**   | Should fix before merge                                            | missing broadcast hint, IoC violation, missing input validation |
| **MINOR**   | Fix if easy, else follow-up                                        | naming oddity, missing docstring on public function |
| **NIT**     | Optional polish                                                   | weak test assertion that's still asserting something |

Confidence is 0-100. Auto-post threshold defaults to 80; security
findings auto-post at 70 (lower bar — false-negatives cost more than
false-positives in security).

---

## 6 · Determinism rules

1. **Never invent file paths or line numbers.** Cite only what's in the diff.
2. **Cite a `rule_id`** that fits the skill's namespace: `injection.*`,
   `secret.*`, `crypto.*`, `py.*`, `java.*`, `perf.*`, `sql.*`, `dep.*`,
   `config.*`, `migration.*`, `api.*`, `arch.*`, `test.*`, `docs.*`,
   `naming.*`, `concurrency.*`, `resource.*`, `err.*`.
3. **Severity is policy-driven**, not vibes-driven. Re-read this file before
   labeling.
4. **Stay in lane.** Each sub-agent has a beat; don't emit findings
   delegated to another sub-agent (the deduper will drop them anyway).
5. **Quantify when possible.** "Scans 50M rows per row · nightly job goes
   from 30 min to 8 days" beats "this is inefficient."

---

## 7 · Graceful degradation (always-on)

Every skill has a deterministic fallback (regex pattern matching) that
runs when the Databricks Claude model is unreachable. The platform
never returns empty findings due to a network outage — it returns
high-precision regex catches plus `fallback_used: true` in telemetry.

---

## 8 · How to add a new skill

1. Create `.github/skills/<your_skill>.py`
2. Subclass `Skill` (from `skills.base`)
3. Decorate with `@register_skill`
4. Implement `should_run(ctx) -> bool` and `async run(ctx, model) -> SkillResult`
5. Add the import in `.github/skills/__init__.py`
6. (Optional) Pull it into a SubAgent's `skills()` list

The Skill registry auto-discovers everything imported. No YAML. No
separate prompt files — the prompt content lives inside the skill module
alongside the deterministic fallback.

---

## 9 · How to add a new sub-agent

1. Create `Agents/SubAgents/<YourAgent>/agent.py`
2. Subclass `SubAgent` (from `Agents.SubAgents.base`)
3. Implement `skills() -> list[str]` returning skill names
4. Implement `async run(ctx, model)` (usually just `return await self._run_skills(ctx, model)`)
5. Register the class in `Agents/SubAgents/__init__.py` and `Agents/MasterAgent/action.py`
6. Add planning logic in `Agents/MasterAgent/planning.py` if conditional

---

## 10 · Public API

```python
from Agents import MasterAgent

agent = MasterAgent()
result = await agent.review_pr(
    pr_id=42, repo="acme/billing", pr_number=42,
    title="Refactor invoice handler", author="alice",
    branch="feat/invoice", diff_text=diff,
)
print(result["verdict"], result["findings_count"])
```

Other entrypoints: `agent.generate_cab_brief(...)`, `agent.generate_scorecard(...)`.
