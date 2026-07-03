PhiStyle OS — Phase Prompts Master Pack
Version: 2026-07-04

Note:
This file consolidates the PhiStyle OS Phase prompts from Phase 1 through Phase 10B.
Early phases are reconstructed into clean, copy-ready Codex prompts based on the implemented architecture.
Phase 7B onward is closer to the actual prompts used in the working development flow.

====================================================================
VERSION NOTES
====================================================================

This document is a handoff and execution guide, not a historical transcript.
Early phases are reconstructed into clean implementation prompts from the current architecture.
Phase 7B onward is closer to the actual working prompts used during development.
When this document conflicts with the live repository, inspect the live repository and prefer the implemented code plus current architecture docs.
When this document conflicts with safety rules, prefer the stricter safety rule.

====================================================================
PHASE INDEX
====================================================================

Phase 1   Platform Scaffold
Phase 2   LLM Router v0
Phase 2.5 Local LLM Roadmap
Phase 3   Database Core
Phase 4   App Registry Core
Phase 5   Agent Runtime Core
Phase 6A  DeepSeek Provider
Phase 6D  LLM Provider Hardening
Phase 6E  Architecture Patch
Phase 7   Daily Brief Agent
Phase 7A  Daily Brief Structured Output Fix
Phase 7B  Code Review Agent Scaffold
Phase 7C  Brain-First Architecture Patch
Phase 8A  Knowledge / Memory Layer Scaffold with NAS Reference Support
Phase 8B  Decision Request Scaffold
Phase 9A  Triage Agent Scaffold
Phase 10A Brain Orchestrator Scaffold
Phase 10B BrainReview to DecisionLog Draft Link

====================================================================
GLOBAL SAFETY RULES
====================================================================

These rules apply to all phases in this document unless a future phase explicitly overrides them with a dedicated Human Approval / Execution Layer.

1. No phase may implement automatic trading, payments, deployments, emails, destructive file operations, or external side effects unless a future explicit execution phase says so.

2. Any field named approved, approved_by, human_approved, recommendation=proceed, required_human_approval, or DecisionLog.status=approved is record-only unless a future Human Approval / Execution Layer explicitly defines side effects.

3. Fable Brain is future advisory brain unless a phase explicitly wires the real Fable API.

4. Gemini is future review provider unless a phase explicitly wires the real Gemini API.

5. DeepSeek is available as a worker/summarizer provider, but decision-system phases must not call it unless explicitly stated.

6. Codex is development-time only. It is not a runtime provider, is not routed to by LLM Router, and PhiStyle OS must not call Codex to modify its own code unless a future self-modifying-agent phase explicitly defines that capability and its risk controls.

7. NAS is cold storage / raw file storage / export storage / backup storage only. Mac mini remains the compute/runtime/database host.

8. Active PostgreSQL data must not live on NAS / SMB / network storage.

9. All PostgreSQL enum migrations must avoid duplicate enum creation. If a migration manually creates enum types, table columns must use PostgreSQL enum objects with create_type=False, or an equivalent safe pattern.

10. Unless explicitly stated otherwise, all phases are advisory-only and must not trigger workflow, approval, trading, deployment, payment, or permission side effects.

Note on Phase 6B / 6C:
Phase 6B / 6C were exploratory provider-testing discussions rather than stable standalone implementation prompts. DeepSeek real API validation is captured under Phase 6A. Fable remains future scope until a dedicated Fable / Brain Mode phase.

Note on Phase 6F:
Phase 6F was referenced as a CI placeholder in Phase 6E but is intentionally not included as a standalone prompt in this pack. If implemented later, it should become:
Phase 6F: CI / Test Gate / No deploy if tests fail.

====================================================================
PHASE 1: Platform Scaffold
====================================================================

Phase 1: Platform Scaffold

Goal:
Create the initial PhiStyle OS platform scaffold.

Scope:
Create a minimal deployable full-stack skeleton.
Do NOT implement investment logic.
Do NOT implement agents yet.
Do NOT implement LLM provider calls yet.
Do NOT modify legacy apps.

Tasks:
1. Create backend scaffold using FastAPI.
2. Create frontend scaffold using Next.js.
3. Create Docker Compose setup for backend and frontend.
4. Add a basic /health endpoint returning {"status":"ok"}.
5. Add root folders: apps/, docs/, services/, shared/, phistyle_platform/ or equivalent.
6. Add .env.example with placeholders only. Do not commit secrets.
7. Add basic README / docs for local development.
8. Ensure Docker build succeeds.
9. Stop after scaffold.

Expected verification:
curl http://localhost:8000/health

====================================================================
PHASE 2: LLM Router v0
====================================================================

Phase 2: LLM Router v0

Goal:
Add a first prototype of the LLM Router so agents and business logic never call provider APIs directly.

Scope:
Do NOT call real providers yet.
Do NOT implement Fable.
Do NOT implement Gemini.
Do NOT modify legacy apps.
Do NOT implement investment logic.

Tasks:
1. Add services/llm_router/ scaffold.
2. Define provider registry concept.
3. Define role-based routing concept:
   - orchestrator
   - deep_reasoner
   - coder
   - fast_worker
   - summarizer
   - reviewer
4. Add basic request/response types.
5. Add router function that accepts a role and prompt/request.
6. Add stub provider behavior.
7. Add docs explaining:
   - business logic requests roles, not providers/models
   - providers are behind adapters
   - Phase 2 is a prototype that Phase 6D may replace internally
8. Add tests for role routing scaffold.
9. Stop after scaffold.

====================================================================
PHASE 2.5: Local LLM Roadmap
====================================================================

Phase 2.5: Local LLM Roadmap

Goal:
Prepare PhiStyle OS for future local LLM serving without implementing local serving yet.

Scope:
Documentation and configuration placeholders only.
Do NOT install Ollama.
Do NOT run vLLM.
Do NOT run SGLang.
Do NOT implement speculative serving.

Tasks:
1. Add provider placeholders for:
   - local_ollama
   - local_vllm
   - local_sglang
   - third_party_proxy
   - speculative_serving
2. Add config placeholders:
   - LOCAL_LLM_PROVIDER=ollama
   - LOCAL_LLM_BASE_URL=http://localhost:11434
   - VLLM_BASE_URL=
   - SGLANG_BASE_URL=
   - ENABLE_SPECULATIVE_SERVING=false
3. Add docs describing local model roadmap.
4. Stop after documentation/config scaffold.

====================================================================
PHASE 3: Database Core
====================================================================

Phase 3: Database Core

Goal:
Add PostgreSQL, SQLAlchemy, and Alembic database foundation.

Scope:
Do NOT implement app-specific business logic.
Do NOT implement vector DB.
Do NOT implement RAG.
Do NOT modify legacy apps.

Tasks:
1. Add PostgreSQL service to docker-compose.yml.
2. Add SQLAlchemy database connection/session layer.
3. Add Alembic migration scaffold.
4. Add initial shared models if appropriate:
   - Company
   - Watchlist
   - Event
   - AgentRun
5. Add docs/database.md covering connection string, migrations, and Docker Postgres.
6. Ensure backend can import database modules.
7. Add tests where appropriate.
8. Stop after scaffold.

Important:
Active PostgreSQL data should live on Mac mini local Docker volume, not NAS/SMB.

====================================================================
PHASE 4: App Registry Core
====================================================================

Phase 4: App Registry Core

Goal:
Add an OS-level App Registry so PhiStyle OS knows what apps exist.

Scope:
Do NOT implement app features.
Do NOT implement investment logic.
Do NOT modify legacy apps except references/import docs if needed.

Tasks:
1. Add App Registry module.
2. Avoid naming a Python package "platform"; use phistyle_platform or equivalent.
3. Register initial apps:
   - capital
   - points-wallet
   - dental-ppt
   - travel
   - snowboard
4. Each app should include id, name, category, status, sensitivity, route, health_endpoint, owner, data_scope.
5. Add GET /apps endpoint.
6. Add tests for /apps.
7. Stop after scaffold.

====================================================================
PHASE 5: Agent Runtime Core
====================================================================

Phase 5: Agent Runtime Core

Goal:
Add the first Agent Runtime so agents can be registered and invoked consistently.

Scope:
Do NOT implement real business agents yet except EchoAgent.
Do NOT call real LLM providers.
Do NOT modify legacy apps.
Do NOT implement investment logic.

Tasks:
1. Add runtime package under existing safe repo structure.
2. Add core runtime concepts:
   - Agent definition
   - Agent registry
   - runtime execution
   - context
   - events placeholder
   - scheduler placeholder
3. Add EchoAgent:
   - id: echo-agent
   - name: Echo Agent
   - role: test
   - returns input message with echo metadata
4. Add endpoints:
   - GET /agents
   - POST /agents/run
5. Add tests.
6. Ensure backend Docker image copies required root packages.
7. Stop after scaffold.

====================================================================
PHASE 6A: DeepSeek Provider
====================================================================

Phase 6A: DeepSeek Provider

Goal:
Add DeepSeek as the first real external LLM provider behind the LLM Router.

Scope:
Do NOT expose API keys.
Do NOT call Fable.
Do NOT call Gemini.
Do NOT implement investment logic.
Do NOT let agents call DeepSeek directly.

Tasks:
1. Add DeepSeek provider adapter behind LLM Router.
2. Use env vars:
   - DEEPSEEK_API_KEY
   - DEEPSEEK_BASE_URL=https://api.deepseek.com
3. Add /llm/test endpoint if not already present.
4. If DEEPSEEK_API_KEY is missing, return dry_run=true.
5. If key exists, call DeepSeek through router/provider adapter.
6. Return provider_id, model, dry_run, content, usage metadata if available.
7. Add docs for secrets.
8. Stop after provider integration.

====================================================================
PHASE 6D: LLM Provider Hardening
====================================================================

Phase 6D: LLM Provider Hardening

Goal:
Harden the LLM Router into a provider-agnostic abstraction layer.

Scope:
Only modify services/llm_router/** unless config path constraints require placing configs inside services/llm_router/config/.
Do NOT modify business apps.
Do NOT modify legacy apps.
Do NOT implement investment logic.

Tasks:
1. Add unified message schema:
   - UnifiedRequest
   - UnifiedMessage
   - ContentBlock
   - UnifiedResponse
   - UnifiedStreamEvent
   - UnifiedUsage
2. Add provider adapter interface:
   - normalize_request()
   - call()
   - normalize_response()
   - normalize_stream_event()
3. Add refusal handling as distinct non-retryable result type.
4. Add config files:
   - llm_providers.yaml
   - llm_routing.yaml
   - llm_retry.yaml
   - llm_pricing.yaml
5. Routing:
   - business code requests role
   - first match wins
   - mandatory fallback
6. Retry:
   - max_retries
   - base_delay_seconds
   - max_delay_seconds
   - backoff_multiplier
   - retry_on_status
   - never_retry_stop_reasons includes refusal
7. Pricing:
   - per million input/output/reasoning tokens
   - no hardcoded pricing in code
8. Usage tracking fields:
   - request_id, timestamp, provider, model, role, agent_id
   - input_tokens, output_tokens, reasoning_tokens, estimated_cost
9. Fable-specific:
   - adaptive thinking cannot be disabled
   - thinking blocks must not be inserted into normal conversation history
   - thinking/reasoning output stored separately or discarded
10. Add docs/llm_provider_abstraction.md.
11. Add tests for normalization, routing, refusal, and thinking separation.
12. Stop after hardening.

====================================================================
PHASE 6E: Architecture Patch
====================================================================

Phase 6E: Roadmap and Architecture Patch

Goal:
Clarify roadmap assumptions and patch architecture risks before continuing.

Scope:
Documentation only.
Do NOT implement real API calls.
Do NOT modify legacy apps.
Do NOT add trading logic.
Do NOT modify Agent Runtime code.
Do NOT create Alembic/SQL migrations.

Tasks:
1. Update roadmap/docs:
   - Phase 2 Router v0 is prototype
   - Phase 6D may replace Phase 2 internals
   - Phase 2 is not legacy
2. Add LLM usage tracking design doc only.
3. Add App ↔ Agent mapping doc.
4. Add secrets management doc.
5. Add human approval principle:
   - no real trades without explicit human confirmation
   - early phases read-only/advisory-only
6. Add Phase 6F CI placeholder. (Note: Phase 6F itself is not included in this pack — it is not listed in the Phase Index and has no dedicated section. Track it separately, or fold its scope into a future phase, before relying on this reference.)
7. Stop after documentation patch.

====================================================================
PHASE 7: Daily Brief Agent
====================================================================

Phase 7: Daily Brief Agent Skeleton

Goal:
Create a DailyBriefAgent that summarizes provided text into a structured brief.

Scope:
Do NOT fetch external news.
Do NOT implement scheduling.
Do NOT persist to database yet.
Do NOT implement investment logic.
Do NOT call Fable.
Do NOT modify legacy apps.

Tasks:
1. Add DailyBriefAgent.
2. Register it in Agent Runtime.
3. Agent:
   - id: daily-brief-agent
   - name: Daily Brief Agent
   - role: summarizer
4. Input:
   {"topic":"AI infrastructure","text":"long text to summarize"}
5. It should use LLM Router role "summarizer".
6. Output:
   {"topic":"...","summary":"...","key_points":[],"risk_flags":[],"source":"manual_input"}
7. Add tests with mocked LLM router output.
8. Add docs/daily_brief_agent.md.
9. Stop after scaffold.

====================================================================
PHASE 7A: Daily Brief Structured Output Fix
====================================================================

Phase 7A: Daily Brief Structured Output Fix

Goal:
Ensure DailyBriefAgent returns true structured fields instead of embedding key points/risk flags inside summary text.

Scope:
Only modify DailyBriefAgent and small parser/test files if needed.
Do NOT fetch news.
Do NOT add persistence.
Do NOT add scheduling.
Do NOT call Fable.
Do NOT modify legacy apps.

Tasks:
1. Update DailyBriefAgent prompt to require strict JSON only.
2. Parse LLM response into summary, key_points, risk_flags.
3. Add safe fallback if JSON parse fails.
4. Add tests with mocked valid JSON and malformed response fallback.
5. Stop after structured output fix.

====================================================================
PHASE 7B: Code Review Agent Scaffold
====================================================================

Phase 7B: Add Code Review Agent scaffold.

Goal:
Add a review-only agent that can review code changes without modifying code.

Scope:
Do NOT implement real Gemini API call yet.
Do NOT modify legacy apps.
Do NOT implement investment logic.
Do NOT auto-merge or auto-approve anything, now or in any future phase.
Recommendation is advisory-only.

Create:

Agent:
- id: code-review-agent
- name: Code Review Agent
- role: reviewer

Input:
{
  "diff": "...",
  "scope": "backend | frontend | llm_router | docs",
  "risk_level": "low | medium | high"
}

Output:
{
  "summary": "...",
  "critical_issues": [],
  "medium_issues": [],
  "low_issues": [],
  "architecture_risks": [],
  "security_risks": [],
  "test_gaps": [],
  "recommendation": "approve | request_changes | escalate_to_fable"
}

Content generation:
- call_llm() must be injectable/mockable.
- Until real Gemini is wired in, call_llm() returns a stub response.
- summary, issue lists, architecture_risks, and security_risks come only from call_llm().
- The agent itself must not do semantic code analysis for those fields.

Deterministic checks:
- secrets detection
- provider logic outside adapters/providers
- test gap detection
- invalid scope/risk_level validation

Secrets detection:
Use regex scan against:
- sk-ant-
- sk-
- API_KEY=
- -----BEGIN PRIVATE KEY-----

Provider logic outside adapters/providers:
If diff touches a file outside */adapters/** and */providers/** and contains known provider names:
- deepseek
- fable
- openai
- ollama
then flag provider-specific logic outside adapters/providers.

Rule priority:
1. secrets -> request_changes
2. provider-specific logic outside adapters/providers -> request_changes
3. high risk_level -> escalate_to_fable
4. behavior changes without tests -> request_changes
5. else approve

Invalid scope/risk_level:
- request_changes
- note in critical_issues

Add docs/code_review_agent.md.
Add tests with call_llm mocked/stubbed.
Do not call real Gemini yet.
Stop after scaffold.

====================================================================
PHASE 7C: Brain-First Architecture Patch
====================================================================

Phase 7C: Brain-First Architecture Patch

Goal:
Clarify that Fable as "Brain" is different from Fable as a normal LLM provider.

Scope:
Documentation only.
Do NOT implement Fable API calls.
Do NOT modify Agent Runtime code.
Do NOT modify LLM Router code.
Do NOT modify legacy apps.
Do NOT modify config/llm_providers.yaml or config/llm_routing.yaml.

Tasks:
1. Add docs/brain_architecture.md.
2. Explain:
   - Provider mode: Fable is called by LLM Router like any other provider.
   - Brain mode: Fable acts as orchestrator that can plan, delegate, review, and decide.
3. Define target architecture:
   Events / User Requests
        ↓
   Triage / Gatekeeper
        ↓
   Brain Orchestrator ←──→ Knowledge / Memory
        ↓
   Agent Runtime
        ↓
   LLM Router
        ↓
   DeepSeek / Gemini / Local Models
4. Define runtime roles:
   - Fable Brain
   - DeepSeek worker/triage
   - Gemini code/execution review
   - Local models private/local tasks
5. Explicitly exclude Codex from runtime.
6. Clarify Router is execution layer, not strategic decision-maker.
7. Clarify Agent Runtime executes tasks but does not own strategic judgment.
8. Add cost-control and memory principles.
9. Add routing overlap note to resolve in Phase 9/10.
10. Add future placeholders:
    - Phase 8 Knowledge / Memory Layer
    - Phase 9 Triage Agent
    - Phase 10 Brain Orchestrator
    - Phase 11 Brain Review Loop
    - Phase 12 Capital App Intelligence
11. Update ROADMAP.md.
12. Stop after documentation patch.

====================================================================
PHASE 8A: Knowledge / Memory Layer Scaffold with NAS Reference Support
====================================================================

Phase 8A: Knowledge / Memory Layer Scaffold with NAS Reference Support

Goal:
Add the first version of a shared Knowledge / Memory layer for PhiStyle OS.

Deployment assumption:
- Mac mini M4 is compute/runtime host.
- Mac mini runs Docker, Backend, Frontend, Agent Runtime, LLM Router, and active PostgreSQL.
- Synology DS220+ NAS is slow and should only be cold storage, large-file storage, exports, and backups.
- Do NOT place active PostgreSQL data directory on NAS / SMB / network storage.

Scope:
Do NOT implement vector search, embeddings, RAG, file upload, NAS reading, PDF parsing, OCR, NAS scanning, investment logic, or trading.
Do NOT call Fable or Gemini.
Do NOT modify legacy apps.

Tasks:
1. Add docs/knowledge_memory_layer.md.
2. Add shared/models/knowledge.py and Alembic migration.

KnowledgeDocument:
- id
- title
- content
- source_type: manual | agent_generated | import
- tags
- storage_backend: local | nas | external
- file_path
- created_at
- updated_at

AgentMemory:
- id
- agent_id
- memory_type: observation | summary | decision_context
- content
- importance: low | medium | high
- created_at

DecisionLog:
- id
- title
- decision
- rationale
- proposed_by
- reviewed_by
- approved_by
- status: proposed | approved | rejected
- related_request_id
- created_at

Important:
- "import" API value must remain "import"; use enum member IMPORT if needed.
- DecisionLog.status=approved must not trigger workflow or action.

Migration Safety Note:
For PostgreSQL enums, avoid duplicate enum creation. If Alembic migration code manually creates enum types with .create(bind, checkfirst=True), then table columns should use PostgreSQL enum objects with create_type=False, or an equivalent safe pattern. Do not create enum types twice through both manual .create() calls and implicit SQLAlchemy table creation.

This note reflects the Phase 8A migration issue where knowledge_source_type was created twice before the migration was corrected.

3. Add shared/services/knowledge_service.py:
   - create/list knowledge document
   - create/list agent memory
   - create/list decision log
4. Add endpoints:
   - GET/POST /knowledge/documents
   - GET/POST /knowledge/memories
   - GET/POST /knowledge/decisions
5. Add tests.
6. Update ROADMAP.md.
7. Stop after scaffold.

====================================================================
PHASE 8B: Decision Request Scaffold
====================================================================

Phase 8B: Decision Request Scaffold

Goal:
Add a structured Decision Request system so PhiStyle OS can represent decisions before any brain/orchestrator makes recommendations.

Scope:
Do NOT call Fable, Gemini, or DeepSeek.
Do NOT implement automatic execution, trading, approval, Capital intelligence, Triage Agent, or Brain Orchestrator.
Do NOT enforce status transition rules in this phase.
Do NOT modify legacy apps.

Tasks:
1. Add docs/decision_request.md.
2. Add shared/models/decision_request.py and Alembic migration.

DecisionRequest:
- id
- app_id
- decision_type
- question
- context
- options
- risk_level
- status
- created_by
- related_knowledge_document_id
- related_decision_log_id
- created_at
- updated_at

Enums:
decision_type:
- investment
- travel
- credit_card
- medical
- engineering
- personal
- architecture

risk_level:
- low
- medium
- high

status:
- draft
- submitted
- triaged
- brain_reviewed
- human_approved
- rejected
- archived

Important:
- options is TEXT/free-form string, not JSON.
- related_knowledge_document_id FK -> knowledge_documents.id ON DELETE SET NULL
- related_decision_log_id FK -> decision_log.id ON DELETE SET NULL
- human_approved is only a record status and has no side effects.

3. Add shared/services/decision_request_service.py:
   - create_decision_request()
   - list_decision_requests()
   - get_decision_request()
   - update_decision_request_status()
4. Add endpoints:
   - GET /decisions/requests
   - POST /decisions/requests
   - GET /decisions/requests/{id}
   - PATCH /decisions/requests/{id}/status
5. Add tests.
6. Update ROADMAP.md.
7. Stop after scaffold.

====================================================================
PHASE 9A: Triage Agent Scaffold
====================================================================

Phase 9A: Triage Agent Scaffold

Goal:
Add a Triage Agent that routes Decision Requests using a deterministic rule engine.

Scope:
Do NOT call Fable, Gemini, or DeepSeek.
Do NOT implement Brain Orchestrator.
Do NOT implement investment logic, execution, trading, or workflows.
Do NOT independently re-assess risk_level.
Do NOT modify legacy apps.

Tasks:
1. Add docs/triage_agent.md.
2. Add SQLAlchemy model and Alembic migration.

Migration note:
Use the Phase 8A PostgreSQL enum lesson. Ensure enum types are created exactly once and avoid duplicate enum creation in Alembic migrations.

TriageResult:
- id
- decision_request_id: FK to decision_requests.id ON DELETE CASCADE
- risk_level
- recommendation
- rationale
- flags
- created_by
- created_at

Enums:
risk_level:
- low
- medium
- high

recommendation:
- handle_locally
- use_worker_model
- escalate_to_brain
- reject_request

3. Add shared/services/triage_service.py:
   - create_triage_result()
   - list_triage_results()
   - list_triage_results_for_request()
   - get_latest_triage_result_for_request()

4. Add deterministic TriageAgent:
- id: triage-agent
- name: Triage Agent
- role: triage

Rules, first match wins:
1. Empty question or context -> reject_request
2. high risk_level -> escalate_to_brain
3. investment or medical -> escalate_to_brain unless low risk and context contains "informational only"
4. engineering + keyword security/secret/deployment/database migration/trading/payment -> escalate_to_brain
5. medium risk -> use_worker_model
6. else -> handle_locally

5. Register Triage Agent.
6. Add endpoints:
   - GET /decisions/triage
   - GET /decisions/requests/{id}/triage
   - POST /decisions/triage/run
   - POST /decisions/triage/override
7. Add tests.
8. Update ROADMAP.md.
9. Stop after scaffold.

====================================================================
PHASE 10A: Brain Orchestrator Scaffold
====================================================================

Phase 10A: Brain Orchestrator Scaffold

Goal:
Add a Brain Orchestrator scaffold that can take a triaged DecisionRequest and produce a structured advisory BrainReview record.

Scope:
Do NOT call real Fable, Gemini, or DeepSeek.
Do NOT implement investment logic, execution, trading, approval, workflow triggers, or DecisionLog auto-creation.
Do NOT modify legacy apps.

Tasks:
1. Add docs/brain_orchestrator.md.
2. Add SQLAlchemy model and Alembic migration.

Migration note:
Use the Phase 8A PostgreSQL enum lesson. Ensure enum types are created exactly once and avoid duplicate enum creation in Alembic migrations.

BrainReview:
- id
- decision_request_id: FK to decision_requests.id ON DELETE CASCADE
- triage_result_id: nullable FK to triage_results.id ON DELETE SET NULL
- recommendation
- rationale
- confidence
- risks
- required_human_approval
- proposed_decision_log_id: nullable FK to decision_log.id ON DELETE SET NULL
- created_by
- created_at

Enums:
recommendation:
- proceed
- request_more_context
- reject
- defer
- human_review_required

confidence:
- low
- medium
- high

3. Add shared/services/brain_review_service.py:
   - create_brain_review()
   - list_brain_reviews()
   - list_brain_reviews_for_request()
   - get_latest_brain_review_for_request()

4. Add deterministic BrainOrchestrator:
- id: brain-orchestrator
- name: Brain Orchestrator
- role: brain

Rules, first match wins:
0. missing/not found/null triage -> human_review_required, confidence high
1. triage_recommendation=reject_request -> reject, confidence medium
2. empty question/context -> request_more_context, confidence high
3. triage_recommendation=escalate_to_brain -> human_review_required, confidence medium
4. risk_level=high -> human_review_required, confidence medium
5. triage_recommendation=use_worker_model -> defer, confidence medium
6. else -> proceed, confidence low

All rules:
required_human_approval = true

5. Register Brain Orchestrator.
6. Add endpoints:
   - GET /decisions/brain-reviews
   - GET /decisions/requests/{id}/brain-reviews
   - POST /decisions/brain/run
   - POST /decisions/brain/override
7. Add tests.
8. Update ROADMAP.md.
9. Stop after scaffold.

====================================================================
PHASE 10B: BrainReview to DecisionLog Draft Link
====================================================================

Phase 10B: BrainReview to DecisionLog Draft Link

Goal:
Add a safe, explicit way to create a draft DecisionLog from an existing BrainReview and link it back to the BrainReview through proposed_decision_log_id.

Scope:
Do NOT call Fable, Gemini, or DeepSeek.
Do NOT implement real Brain reasoning.
Do NOT implement investment logic, execution, trading, approval, or workflow triggers.
Do NOT auto-create a DecisionLog during POST /decisions/brain/run.
Do NOT change DecisionRequest.status automatically.
Do NOT treat DecisionLog.status=approved as an execution approval.
Do NOT modify legacy apps.

No-Migration Expected Note:
No Alembic migration is expected in Phase 10B unless implementation discovers a missing column. BrainReview.proposed_decision_log_id should already exist from Phase 10A. This phase should primarily add service logic, endpoint logic, docs, and tests.

Tasks:
1. Add docs/brain_review_to_decision_log.md covering:
   - BrainReview = advisory analysis
   - DecisionLog = durable recorded decision
   - this phase creates proposed DecisionLog drafts only
   - no approval/execution/trading/deploy/payment/email/automation
   - proposed_decision_log_id is populated only by explicit endpoint
   - POST /decisions/brain/run must not create DecisionLog automatically
   - DecisionLog.status=proposed default
   - DecisionLog.status=approved remains record-only
   - human approval workflow is future scope

2. Add shared/services/brain_decision_link_service.py with:
   - create_decision_log_draft_from_brain_review()

Behavior:
- Input: brain_review_id, proposed_by / approved_by optional free-text fields if needed.
- Load BrainReview by id.
- Load related DecisionRequest.
- Create DecisionLog with:
  - title derived from DecisionRequest.question
  - decision derived from BrainReview.recommendation
  - rationale derived from BrainReview.rationale
  - proposed_by = BrainReview.created_by or provided override
  - reviewed_by = BrainReview.created_by
  - approved_by = null or provided value only if schema requires it
  - status = proposed
  - related_request_id = string form of DecisionRequest.id or existing convention
- Update BrainReview.proposed_decision_log_id.
- Return both IDs or response object.

Rules:
- No LLM/Fable/Gemini/DeepSeek/network calls.
- No action execution.
- No DecisionRequest status mutation.
- No approval side effects.
- approved_by is metadata only and must not trigger approval or execution side effects.
- No workflow triggers.
- Idempotency: if BrainReview already has proposed_decision_log_id, do not create duplicate DecisionLog.

3. Add endpoint:
POST /decisions/brain-reviews/{id}/decision-log-draft

Request:
{
  "proposed_by": "brain-orchestrator",
  "approved_by": null
}

approved_by should normally be null in this phase. If provided, it is copied only as record metadata and must not imply approval, human authorization, execution permission, or workflow activation.

Response first call:
{
  "brain_review_id": 1,
  "decision_log_id": 1,
  "decision_log_status": "proposed",
  "created": true
}

Response second call:
{
  "brain_review_id": 1,
  "decision_log_id": 1,
  "decision_log_status": "proposed",
  "created": false
}

Validation:
- BrainReview id must exist.
- Linked DecisionRequest must exist.
- If proposed_decision_log_id exists and points to a DecisionLog, return it.
- If proposed_decision_log_id points to missing DecisionLog, error consistently with backend style.

4. Update BrainReview response schema if needed so proposed_decision_log_id is visible.
5. Add tests:
   - create draft
   - link updated
   - status proposed
   - idempotency
   - brain/run still does not create DecisionLog
   - no DecisionRequest status mutation
   - no approval/action side effects
   - invalid BrainReview rejected
   - no LLM/network calls
6. Update ROADMAP.md.
7. Stop after scaffold.

====================================================================
END OF FILE
====================================================================
