# ChangePilot Studio

> **The Intelligent Platform for Reviews, Governance & Releases.**
>
> AI co-pilot for engineering at Fiserv Data Platform. Four capabilities, one runtime, one decision ledger.

---

## What's in this single repo

This is the **unified project**: the AI agent content layer + the FastAPI runtime + the React UI, all in one place. Open the root in VS Code and everything below is ready to develop, test, and run.

```
ChangePilot-Studio/
│
├── backend/                     ← FastAPI runtime (Python 3.11)
│   ├── app/                     ← REST API · agent orchestrator · workers · DB models
│   ├── prompts/                 ← Runtime prompts (snapshot of Agents/<X>/prompt.md)
│   ├── rules/                   ← Runtime rule packs (snapshot of ReviewEngines/<X>/rules.yaml)
│   ├── scripts/                 ← seed_demo.py · migrations
│   ├── tests/                   ← pytest suite
│   ├── atlas.db                 ← SQLite dev DB (pre-seeded with 18 PRs / 92 findings)
│   ├── pyproject.toml
│   └── .env                     ← LLM credentials (DATABRICKS_HOST + DATABRICKS_TOKEN)
│
├── frontend/                    ← React 18 + Vite + Tailwind + TypeScript
│   ├── src/                     ← Inbox · Triage · Insights · Scorecard · CABBriefs · Ledger · Settings
│   ├── package.json
│   └── vite.config.ts
│
├── Agents/                      ← Canonical AI personas (10 agents · spec.md + prompt.md each)
├── Specs/                       ← Output contracts (Finding schema · CAB templates · Scorecard defs)
├── ReviewEngines/               ← Per-technology rule packs (PySpark · Spark · Java · SpringBoot · Python · SQL · Databricks · Terraform · Kubernetes · Generic)
├── Shared/                      ← Cross-cutting policy (severity · tone · types · language detection)
├── Workflows/                   ← Multi-agent compositions (PRReview · CAB · Release · Governance)
├── Services/                    ← Enterprise integration specs (GitHub · Databricks · Jira · Slack · etc.)
├── Models/                      ← LLM provider configs (DatabricksServing ⭐ · Claude · OpenAI · Local)
├── APIs/                        ← OpenAPI contract specs
├── Docs/                        ← QUICKSTART · how-to-add-* · runbook-for-leadership
├── Tests/                       ← Cross-cutting consistency tests
├── Data/                        ← Runtime state (gitignored)
├── UI/                          ← Placeholder · the runtime UI lives in frontend/
│
├── .github/                     ← Copilot instructions + skill domains
│   ├── copilot-instructions.md
│   ├── instructions/            ← 23 shim files pointing into Agents/ + ReviewEngines/
│   └── skills/                  ← 9 skill domains × {skill.md, examples/, checklists/, templates/}
│
├── .tools/                      ← Portable Node.js 20.18 LTS (no admin install needed)
├── .vscode/                     ← VS Code workspace settings + extension recommendations
├── start.ps1                    ← One-command launcher
├── setup.ps1                    ← First-time installer
├── ChangePilot-Studio.code-workspace ← VS Code multi-root workspace
├── README.md
├── CHANGELOG.md
└── .gitignore
```

---

## First-time setup (5 minutes)

```powershell
cd "C:\Users\Harendra Singh\ChangePilot-Studio"
.\setup.ps1
```

What it does:
1. Creates `backend/.venv` Python virtual environment
2. Installs Python dependencies via `pip install -e .` (FastAPI + SQLAlchemy + LiteLLM + ADK + …)
3. Adds portable Node.js to PATH for this session
4. Runs `npm install` in `frontend/` (React + Tailwind + Framer Motion + …)
5. Optionally seeds the demo DB (`scripts/seed_demo.py`) if you want sample data immediately

After setup, edit `backend/.env` with your Databricks credentials.

---

## Day-to-day commands

```powershell
.\start.ps1                # Backend + frontend, hot-reload both
.\start.ps1 -Backend       # Backend only
.\start.ps1 -Frontend      # Frontend only
.\start.ps1 -Stop          # Kill both servers
.\start.ps1 -Test          # Run pytest
.\start.ps1 -Clean         # Wipe venv + node_modules + atlas.db (start fresh)
```

When running, the UI is at **http://127.0.0.1:5173** and the FastAPI docs are at **http://127.0.0.1:8000/docs**.

---

## Verify the agent content layer

```powershell
# Run the v2.0 consistency suite (validates Agents + ReviewEngines + shims + uniqueness)
backend\.venv\Scripts\python.exe Tests\consistency\consistency_tests.py
# expected: 82 PASS · 0 FAIL · 3 non-blocking YAML warnings
```

---

## The 10 agents

| Agent | Role | Maturity |
|---|---|---|
| **PRReviewAgent**         | Master orchestrator · 5 dimensions · per-finding confidence | Production |
| **SecurityReviewAgent**   | Security lens · injection · secrets · PII · weak crypto | Production |
| **PerformanceReviewAgent**| Performance lens · Spark · O(n²) · I/O | Production |
| **TestCoverageAgent**     | Coverage lens · missing tests · weak assertions | Production |
| **CABDocumentAgent**      | Auto-generates Standard Change briefs for ServiceNow / JIRA | Beta |
| **GovernanceAgent**       | Architecture · naming · ownership · release rules | Beta |
| **ReleaseReadinessAgent** | Aggregates everything into READY / NOT READY + risk score | Beta |
| **DocumentationAgent**    | Auto-refreshes runbooks / READMEs / data dictionaries | Stub |
| **ScorecardAgent**        | Per-team Engineering Health Scorecard (SQL aggregation) | Stub |
| **LearningFeedbackAgent** | Continuous tuning of rule confidence from accept/dismiss | Stub |

See `Agents/README.md` for the catalog with structure and how to add a new one.

---

## How code review flows through

```
GitHub webhook → backend/app/api/v1.py (webhook handler)
  → backend/app/workers/review_job.py
    → backend/app/agents/orchestrator.py
      → loads prompts from prompts/ (snapshot of Agents/*/prompt.md)
      → loads rules from rules/ (snapshot of ReviewEngines/*/rules.yaml)
      → calls Databricks Claude via backend/app/agents/databricks_claude.py
    → backend/app/core/confidence.py (auto-post threshold)
    → backend/app/db/models.py (persist findings + audit)
    → backend/app/github/client.py (post comments)
React UI ← backend/app/api/v1.py + intelligence.py (Scorecard · CAB · Ledger)
```

---

## Production / runtime notes

- **LLM**: Databricks Model Serving (`databricks/<endpoint>`) via LiteLLM. No public-API Claude in production (`Models/DatabricksServing/` is canonical).
- **No LangChain anywhere** (Fiserv constraint). Google ADK + direct litellm only.
- **Tier 3 policy locked**: comments only · no auto-commit · no auto-merge · no branch creation.
- **Confidence threshold** (default 80) controls auto-post vs human triage.

---

## Adding things

| Want to add... | Read |
|---|---|
| A new agent | `Docs/how-to-add-an-agent.md` |
| A new review engine (language / tech) | `Docs/how-to-add-a-review-engine.md` |
| A new service integration | `Docs/how-to-add-a-service-integration.md` |

---

## Pitch for leadership

See `Docs/runbook-for-leadership.md` — the 3-pillar value story (Reviews · Governance · Releases), ROI per capability, and the next-quarter roadmap.

---

## License

Internal Fiserv use. Do not distribute outside the org.
