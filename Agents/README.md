# Agents — single source of truth

All AI agent logic lives here. The backend is a thin FastAPI wrapper that
delegates to `MasterAgent`. The frontend is a UI that consumes backend
responses. Neither contains agent logic of its own.

## Layout

```
Agents/
├── __init__.py
├── README.md
│
├── Core/                          ← Shared primitives every agent uses
│   ├── model.py                   ← Databricks-hosted Claude adapter (LiteLLM-backed)
│   ├── memory.py                  ← AgentMemory + per-repo learning snapshots
│   ├── observability.py           ← Correlation IDs · trace spans · token estimation
│   └── schemas.py                 ← Canonical Pydantic contracts (Finding, PRContext, etc.)
│
├── MasterAgent/                   ← Top-level orchestrator with explicit P/R/P/A modules
│   ├── agent.py                   ← MasterAgent class + run_master_agent helper
│   ├── perception.py              ← Diff parsing → PRContext
│   ├── reasoning.py               ← Signals inferred from PRContext + memory
│   ├── planning.py                ← ExecutionPlan: which SubAgents to invoke
│   └── action.py                  ← Bounded-parallel SubAgent execution + aggregation
│
├── SubAgents/                     ← Specialized workers, each owns a slice
│   ├── base.py                    ← SubAgent ABC + SubAgentResult
│   ├── CodeReviewAgent/           ← Correctness · style · docs · test gaps
│   ├── SecurityReviewAgent/       ← Always-on · injection · secrets · crypto · deps
│   ├── PerformanceReviewAgent/    ← Perf · concurrency · resource leaks
│   ├── ArchitectureAgent/         ← Layer integrity · API contracts · DB migrations
│   ├── TestCoverageAgent/         ← Standalone test-quality lens
│   ├── DependencyAuditAgent/      ← Supply chain · CVE detection · pin hygiene
│   ├── GovernanceAgent/           ← Naming · ownership · release rules
│   ├── CABDocumentAgent/          ← 8-section ServiceNow Standard Change
│   ├── ScorecardAgent/            ← Per-team narrative + grade + risk signals
│   └── ReleaseReadinessAgent/     ← READY / NOT READY verdict + risk score
│
├── .github/skills/                        ← 17 reusable skills (Python classes · structured I/O)
│   ├── base.py                    ← Skill ABC + global registry
│   ├── _patterns.py               ← Shared regex pattern library
│   ├── _llm_helper.py             ← Shared LLM call helpers
│   ├── code_quality.py
│   ├── security_scan.py
│   ├── performance_analysis.py
│   ├── architecture_validation.py
│   ├── test_coverage_analysis.py
│   ├── dependency_audit.py
│   ├── configuration_validation.py
│   ├── database_migration.py
│   ├── api_contract_validation.py
│   ├── error_handling_review.py
│   ├── concurrency_analysis.py
│   ├── resource_management.py
│   ├── documentation_quality.py
│   ├── governance_compliance.py
│   ├── cab_section_generation.py
│   ├── scorecard_narration.py
│   └── risk_assessment.py
│
└── Prompts/                       ← LLM prompt content lives inside the skill modules.
                                     (no separate template files · keeps Skills self-contained)
```

## Lifecycle (every MasterAgent invocation)

```
PERCEIVE     Perception.build()       → PRContext
RECALL       AgentMemory.snapshot_for() → RepoMemorySnapshot
REASON       Reasoning.infer()        → Signals
PLAN         Planning.plan()          → ExecutionPlan (which SubAgents)
ACT          Action.execute()         → ActionOutcome (aggregated findings + verdict)
REMEMBER     AgentRunRecord persisted, response payload returned
```

Each phase is a separate module so it can be unit-tested or swapped
independently. The MasterAgent class wires them together.

## How a new Skill is added

1. Create `.github/skills/your_skill.py` · subclass `Skill` · decorate with `@register_skill`
2. Implement `should_run(ctx)` and `async run(ctx, model)`
3. Add the import in `.github/skills/__init__.py`
4. Optionally pull it into a SubAgent's `skills()` list

The Skill registry auto-discovers everything imported.

## How a new SubAgent is added

1. Create `SubAgents/YourAgent/agent.py` · subclass `SubAgent`
2. Define `skills()` returning the list of skill names to invoke
3. Implement `async run(ctx, model)` (most use `self._run_skills(ctx, model)`)
4. Register the class in `SubAgents/__init__.py` and `MasterAgent/action.py`
5. Add planning logic in `MasterAgent/planning.py` if it should run conditionally

## Public API

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

## Configuration

No hardcoded teams, repos, or organization specifics. Everything is
driven from:
- `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_MODEL_SERVING_ENDPOINT`
  (model adapter)
- Per-request inputs (PR metadata + diff text)
- Per-repo memory snapshot (optionally backed by host app DB)

## Production-mode vs. degraded-mode

Every Skill is built with graceful degradation: if the Databricks model
is unreachable, the Skill's deterministic pattern pass still produces
findings. So a network outage to Databricks never returns empty output
— you get high-precision regex-based catches instead and `fallback_used: true`
flagged in telemetry.
