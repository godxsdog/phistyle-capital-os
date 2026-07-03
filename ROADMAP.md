# Roadmap

## Current Platform Phases

PhiStyle OS is moving in platform-first phases before any investment-specific
logic is implemented.

### Phase 1: Platform Scaffold
- Create the minimum runnable backend, frontend, Docker, and environment
  foundation.
- Keep legacy apps as references only.

### Phase 2: LLM Router v0 / Prototype
- Introduce the first LLM Router architecture.
- Define model roles, provider registry concepts, and initial routing policy.
- This phase is a prototype, not a final provider abstraction.
- The Phase 2 router is not legacy. It is allowed to evolve in place.

### Phase 2.5: Local Model Serving Roadmap
- Document the future path for Ollama, vLLM, SGLang, speculative serving, and
  cheap third-party DeepSeek-style APIs.
- Keep private data on local providers unless explicitly approved otherwise.

### Phase 3: Database Core Scaffold
- Add database connection scaffolding, initial models, and migration structure.
- Do not ingest real investment data yet.

### Phase 4: App Registry Core
- Register OS-level app metadata.
- Keep imported legacy apps registered only as future apps.

### Phase 5: Agent Runtime Core
- Add app-agnostic agent registration, listing, manual runs, and run result
  recording.
- No background jobs or real trading actions yet.

### Phase 6A-6C: Provider Adapter Scaffolds
- Add DeepSeek and Fable provider adapter scaffolds.
- DeepSeek may be the first provider tested for low-risk text tasks.
- Fable remains reserved for orchestrator and high-risk reasoning use cases.

### Phase 6D: LLM Provider Abstraction Hardening
- Replace Phase 2 router internals where needed.
- Keep the router concept alive while removing assumptions that every provider
  behaves like an OpenAI-compatible chat API.
- Add unified message, response, streaming, refusal, retry, routing, pricing, and
  usage-tracking schemas.

### Phase 6E: Roadmap and Architecture Patch
- Clarify that Phase 2 was Router v0 / prototype only.
- Add plans for persistent LLM usage tracking, App/Agent mapping, secrets
  management, human approval, and CI.
- After this patch, resume Phase 6D as previously scoped before continuing
  DeepSeek/Fable provider work.

### Phase 6F: CI Placeholder
- Run CI on push.
- Run `pytest`.
- Run lint checks.
- Do not deploy if tests fail.

### Phase 7C: Brain-First Architecture Patch
- Document the difference between Fable provider mode and Fable Brain mode.
- Clarify that the LLM Router is an execution layer, not the strategic
  decision-maker.
- Define the future Brain-first flow across Triage, Brain Orchestrator,
  Knowledge / Memory, Agent Runtime, and LLM Router.
- See `docs/brain_architecture.md`.

### Phase 8: Knowledge / Memory Layer
- Store summaries and future decision context for Brain use.
- Keep Brain reads summary-first by default.

### Phase 8A: Knowledge / Memory Layer Scaffold
- Add relational Knowledge / Memory tables and simple create/list endpoints.
- Stay pre-RAG, pre-embedding, pre-vector-search, and pre-Brain-Orchestrator.
- NAS support is reference-only through metadata and `file_path`.
- Active PostgreSQL stays on Mac mini local storage, not NAS, SMB, or network
  storage.

### Phase 8B: Decision Request Scaffold
- Add structured records for decision questions before triage or Brain review.
- Stay pre-Triage, pre-Brain-Orchestrator, and pre-execution.
- Record questions, context, free-form options, risk, status, and related
  Knowledge / Decision Log links.
- Known gap: no status state-machine enforcement yet.

### Phase 9: Triage Agent
- Add low-cost triage before waking the Brain.
- Resolve how triage escalation relates to Phase 7B's `escalate_to_fable`
  recommendation pattern.

### Phase 9A: Triage Agent Scaffold
- Add deterministic Triage Agent and persisted TriageResult records.
- Stay pre-Fable and pre-Brain-Orchestrator.
- Escalation is advisory-only and does not call Fable.
- `risk_level` is passthrough only, not independently reassessed.

### Phase 10: Brain Orchestrator
- Implement Brain mode as an orchestrator that can plan, delegate, review, and
  decide.
- Define Decision Log schema and its relationship to `llm_usage_log`.

### Phase 10A: Brain Orchestrator Scaffold
- Add deterministic Brain Orchestrator and persisted BrainReview records.
- Stay pre-Fable and advisory-only.
- No execution layer exists yet.
- Rule 0 makes missing triage default to human review; this is a deliberate
  safety default, not a gap.

### Phase 10B: BrainReview to DecisionLog Draft Link
- Link advisory BrainReview records to durable DecisionLog drafts.
- Draft creation is explicit and idempotent.
- Generated DecisionLog status is always `proposed`.
- Generated DecisionLog `approved_by` is always null.
- No human approval workflow or execution layer exists yet.
- Stay pre-Fable.
- No migration is expected in this phase.

### Phase 11: Human Review / Approval Loop
- Close the decision-record loop with explicit human approve/reject.
- Update DecisionLog and DecisionRequest records atomically.
- Allow one final HumanReview per DecisionLog.
- Keep approval advisory and record-only.
- No execution layer exists yet.

### Phase 12: Capital App Intelligence
- Begin Capital app intelligence work after the Brain and Memory foundations are
  clear.

## Future Product Phases

These remain future work and should not be started until the platform foundation
is stable.

### Investment Data and Briefing
- News ingestion.
- Price ingestion.
- Watchlist.
- Morning report.
- LINE alerts.

### Analysis and Ranking
- Earnings transcript parsing.
- CapEx extraction.
- Scoring system.
- Ranking dashboard.

### Portfolio and Risk
- Portfolio tracking.
- Risk alerts.
- Backtests.
- Alert rules.

### Multi-Agent Intelligence
- Multi-agent workflow.
- Memory summaries.
- Knowledge graph.
- Strategy evaluation.
