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
