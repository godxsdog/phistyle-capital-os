# Current Repository Analysis

Date: 2026-07-03

Scope read:

- `README.md`
- `PROJECT.md`
- `ROADMAP.md`
- `AGENTS.md`
- `CLAUDE.md`
- `CODEX_FIRST_PROMPT.md`
- everything under `docs/`
- everything under `prompts/`
- repository file and folder structure

## 1. Current Architecture

The repository is currently a seed/constitution repository, not yet an implemented application.

Current structure:

```text
phistyle-capital-os/
├─ README.md
├─ PROJECT.md
├─ ROADMAP.md
├─ AGENTS.md
├─ CLAUDE.md
├─ CODEX_FIRST_PROMPT.md
├─ docs/
│  ├─ architecture.md
│  ├─ philosophy.md
│  ├─ scoring.md
│  └─ workflow.md
└─ prompts/
   ├─ coder.md
   ├─ planner.md
   └─ reviewer.md
```

Architecturally, it describes an AI-first investment operating system with this intended flow:

```text
User
  -> Dashboard
  -> Backend API
  -> Agents
  -> Database
  -> LLM Gateway
  -> Data Sources
```

The intended initial stack is documented as:

- FastAPI backend
- Next.js frontend
- PostgreSQL
- SQLAlchemy / Alembic, implied by the first prompt
- Redis
- Qdrant
- n8n
- Open WebUI
- multi-agent workflow

There is no current `backend/`, `frontend/`, `database/`, `agents/`, `workflows/`, `scripts/`, `config/`, or `tests/` implementation. The repository only defines direction, priorities, workflow, and AI-agent operating rules.

## 2. Current Philosophy

The current philosophy is sharply investment-focused.

Core belief:

- The system should not summarize all news.
- It should identify events that materially change investment decisions.
- The highest-value signal is capital flow, especially AI infrastructure CapEx.
- News is secondary unless it changes capital allocation, supply-chain transmission, or risk.

The investment philosophy can be summarized as:

```text
We do not buy news.
We buy capital flow.
Capital flow follows infrastructure.
Infrastructure follows CapEx.
Therefore, CapEx is the first-class signal.
```

The scoring philosophy is evidence-first:

- Fundamental events: 30
- Supply-chain transmission: 20
- Capital flow / passive flow: 20
- Technical setup: 15
- Risk penalty: 15

The system must explain each score with evidence and produce decision labels:

- Bull
- Neutral
- Bear

The engineering philosophy is also explicit:

- GPT-5.5 is reserved for architecture, high-risk logic, database design, scoring logic, security, and final review.
- Codex implements code changes.
- Mini models handle formatting, docs, comments, renames, and low-risk batch work.
- Planner writes task plans, not code.
- Reviewer reviews, not rewrites.

## 3. What This Project Is Trying To Become

The repository is trying to become an AI investment workflow operating system.

Its target product appears to be:

- a daily decision engine for AI infrastructure and related capital markets;
- a workflow that ingests news, prices, earnings, CapEx, macro, supply-chain, and technical signals;
- a multi-agent system that turns raw data into ranked investment decisions;
- a dashboard for monitoring signals, scores, watchlists, reports, alerts, and eventually portfolio/risk;
- an alerting system that pushes only decision-changing events, not every news item.

The roadmap implies this maturity path:

1. Basic ingestion and morning report.
2. Earnings transcript parsing and CapEx extraction.
3. Portfolio/risk/backtest/alert rules.
4. Multi-agent workflow, memory summaries, knowledge graph, and strategy evaluation.

The project is not trying to be a generic chatbot. Its stated identity is an operating system for investment workflow.

## 4. What Is Missing

The repository is missing nearly all implementation scaffolding.

Missing product/app structure:

- No backend service.
- No frontend app.
- No dashboard implementation.
- No database schema.
- No agent implementation.
- No data ingestion pipelines.
- No queue/job system.
- No alerting implementation.
- No tests.
- No local development setup.
- No deployment setup.

Missing technical contracts:

- API boundaries.
- Data source contracts.
- Database schema.
- Event model.
- Scoring input/output schema.
- Agent interfaces.
- Prompt versioning strategy beyond three role prompts.
- Alert rules and delivery channels.
- Authentication and secrets policy.
- Observability/logging design.
- Error handling and retry policy.

Missing product decisions:

- Watchlist definition.
- Supported markets/tickers/sectors.
- Exact data providers.
- Price data source.
- News source.
- Earnings transcript source.
- CapEx extraction methodology.
- Backtest assumptions.
- Portfolio model.
- Risk model.
- Human approval points.
- What constitutes a decision-changing event.

Missing governance:

- No explicit security model.
- No financial disclaimer or intended-use boundary.
- No data licensing notes.
- No model evaluation criteria.
- No score audit trail policy.
- No hallucination/evidence verification policy beyond “evidence before opinion.”

## 5. What Technical Debt Exists

Because the repository is still mostly documentation, the technical debt is architectural debt rather than code debt.

Current debt:

- The name `PhiStyle Capital OS` suggests the whole OS is investment-specific, which may conflict with any future broader personal OS direction.
- Architecture is described in one line and lacks module boundaries.
- Roadmap is product-oriented but not mapped to folders, services, schemas, or milestones.
- `CODEX_FIRST_PROMPT.md` asks for many technologies at once, which risks over-scaffolding before domain contracts are clear.
- Agent routing rules exist, but no actual agent interface or handoff protocol exists.
- The scoring model is defined as weights, but inputs, evidence requirements, and calculation semantics are not specified.
- Workflow times are defined, but no scheduler/job execution model exists.
- “LLM Gateway,” “Agents,” “Data Sources,” and “Dashboard” are named but not bounded.
- No testing strategy exists for investment logic, scoring, ingestion, or prompt outputs.
- No separation between platform concerns and investment app concerns.
- No explicit storage strategy for raw data, normalized events, generated reports, embeddings, and audit logs.

Potential future debt if implemented directly from the first prompt:

- Too many infrastructure components may be introduced before there is a working domain model.
- n8n, Qdrant, Open WebUI, Redis, PostgreSQL, FastAPI, and Next.js may create operational weight before core ingestion/scoring is validated.
- A monorepo scaffold without ownership rules may become folders without boundaries.
- Agent prompts may drift from actual app/service APIs if not versioned and tested.

## 6. Whether The Repository Structure Is Scalable

The current structure is scalable as a seed constitution, but not scalable as an application repository.

What scales well:

- Clear top-level mission.
- Clear model-role routing philosophy.
- Clear investment worldview.
- Small docs are easy to read.
- Roadmap is simple and phased.
- Prompt roles are separated into planner, coder, reviewer.

What does not scale yet:

- No app/service/platform separation.
- No package/module ownership.
- No place for backend, frontend, jobs, agents, data contracts, schemas, tests, or deployment.
- No clear boundary between investment domain logic and AI orchestration.
- No directory for prompts by workflow or agent.
- No data model hierarchy for raw, normalized, scored, and reported artifacts.
- No mechanism to keep evidence, score, and report generation auditable.

The repository is currently appropriate for project kickoff. It is not yet appropriate for multiple developers, multiple agents, or production-like execution.

## 7. Suggestions For Improvement

### Rename The Conceptual Boundary

If this remains investment-only, `PhiStyle Capital OS` is coherent.

If it is meant to become a broader personal operating system, separate:

- `PhiStyle OS`: platform / personal operating system.
- `Capital`: investment app inside the OS.

This prevents Capital from owning platform concepts like auth, registry, notifications, jobs, and storage.

### Define Architecture Before Scaffolding

Before generating large code scaffolding, define:

- apps
- platform modules
- services
- agents
- shared libraries
- data ownership
- API boundaries
- sensitivity/security classes

Without this, the first implementation may hard-code investment assumptions into platform layers.

### Add A Target Repository Map

Recommended future structure if the project remains investment-first:

```text
backend/
frontend/
agents/
services/
database/
workflows/
prompts/
docs/
tests/
config/
scripts/
```

Recommended future structure if it becomes a broader personal OS:

```text
apps/
platform/
services/
shared/
agents/
docs/
prompts/
workflows/
tests/
config/
scripts/
```

### Specify Data Contracts

Add schemas for:

- raw news item
- normalized event
- company/ticker entity
- CapEx evidence
- earnings transcript excerpt
- supply-chain relation
- price snapshot
- score input
- score output
- alert
- daily report
- portfolio position

### Define Agent Contracts

For each agent, define:

- input
- output
- allowed tools
- evidence requirements
- failure behavior
- when human review is required

Initial agents could be:

- News Agent
- Earnings Agent
- Macro Agent
- Supply Chain Agent
- Scoring Agent
- Report Agent
- Reviewer Agent

### Make Evidence Auditable

Every score and recommendation should preserve:

- source URL or provider id
- timestamp
- extracted quote or fact
- extraction method
- model/prompt version
- confidence
- reasoning summary
- downstream score impact

### Keep Infrastructure Incremental

Avoid turning the seed repo into a large but hollow stack.

Recommended sequence:

1. Define data contracts.
2. Build one ingestion path.
3. Build one normalized event table.
4. Build one scoring prototype.
5. Build one daily report.
6. Add queue/cache/vector store only when the workflow needs it.

### Clarify Security And Compliance

Add docs for:

- secrets handling
- API keys
- provider licensing
- financial decision disclaimer
- human-in-the-loop requirements
- alert risk controls
- audit log retention

### Expand Prompt Governance

Move from role prompts only to versioned workflow prompts:

```text
prompts/
├─ roles/
├─ agents/
├─ reports/
├─ scoring/
└─ review/
```

Each prompt should declare:

- purpose
- inputs
- output schema
- prohibited behavior
- evaluation checks

### Add Acceptance Criteria To Roadmap

Each phase should define:

- deliverables
- tests
- data sources
- operator workflow
- failure modes
- acceptance criteria

Example:

Phase 1 is not just “News ingestion.” It should specify which sources, how often, what schema, what dedupe rules, and what counts as a successful morning report.

### Preserve The Strong Philosophy

The strongest part of the repo is its clarity:

- decision-changing events only;
- CapEx first;
- capital flow first;
- evidence before opinion;
- agents have roles;
- GPT-5.5 is reserved for high-risk decisions.

The next architecture should preserve that clarity while adding boundaries, contracts, and testability.

