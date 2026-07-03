# Knowledge / Memory Layer

Date: 2026-07-03

Status: Phase 8A scaffold. This is pre-RAG, pre-embedding,
pre-vector-search, and pre-Brain-Orchestrator.

## Purpose

The Knowledge / Memory Layer gives PhiStyle OS a shared place to store summaries,
agent memory, and strategic decision records.

This layer is required before Brain Orchestrator work because the future Fable
Brain must be able to read prior summaries and write strategic decisions without
depending on raw full context every time.

## Core Stores

| Store | Purpose |
| --- | --- |
| `llm_usage_log` | Future Phase 6E usage/cost log for provider, model, role, token counts, and estimated cost. |
| `decision_log` | Strategic decision records. This is not an approval engine. |
| `agent_memory` | Agent observations, summaries, and decision context. |
| `knowledge_documents` | Metadata, summaries, extracted snippets, tags, and optional source file references. |

`llm_usage_log` records model usage and cost metadata. `decision_log` records
strategic decisions. They may later share a request id for correlation, but they
serve different purposes.

## Why Phase 8A Avoids RAG

Phase 8A intentionally does not add vector databases, embeddings, or RAG. The
first milestone is a boring, inspectable persistence layer:

- simple relational tables;
- explicit enums;
- manual create/list API endpoints;
- optional file path references only;
- no file ingestion;
- no automatic parsing.

Embeddings, vector search, RAG, and ingestion belong in later phases after the
storage boundary is stable.

## Brain Orchestrator Use

Future Brain Orchestrator work should use this layer to:

- read summaries before requesting raw full context;
- write strategic decisions to `decision_log`;
- store reusable decision context in `agent_memory`;
- reference source files through `knowledge_documents.file_path` when evidence
  exists outside Postgres.

This `DecisionLog` schema is the initial version referenced as a placeholder in
Phase 7C. Phase 10 Brain Orchestrator may extend it.

## Privacy and Local-First Principles

- Prefer local storage and local execution for private data.
- Store summaries and metadata before storing raw full context.
- Do not store large binary files in Postgres.
- Do not send private memory to third-party providers without an explicit future
  policy and approval path.
- Keep API keys and secrets out of documents, memory, logs, and decision records.

## NAS Deployment Principle

- Mac mini is the compute/runtime/database host.
- Mac mini runs Docker, Backend, Frontend, Agent Runtime, LLM Router, and active
  PostgreSQL.
- Synology DS220+ NAS is cold storage, large-file storage, exports, and backups.
- NAS is not a compute node.
- Do not run agents, embeddings, vector search, PDF parsing, OCR, or LLM
  workloads on NAS.
- Postgres stores metadata, summaries, and file references only.
- Postgres does not store large binary files.
- Active PostgreSQL data must not live on NAS, SMB, or network storage.

`knowledge_documents.file_path` is only a reference in Phase 8A. The system does
not read the path, validate that it exists, scan folders, parse files, or ingest
NAS contents.

Example references:

```text
/Volumes/PhiStyleOS/travel/maldives/ana_booking.pdf
/Volumes/PhiStyleOS/dental/case_001/photos/
/Volumes/PhiStyleOS/capital/reports/ai_infra_report.pdf
```

## Approval Boundary

`POST /knowledge/decisions` only persists a record of a decision made elsewhere.
Calling it does not constitute approval and does not trigger approval workflows,
automation, trading, deployment, permission changes, or agent execution.

Real approval workflow enforcement is future scope for Phase 10 and later.

## Phase 8A Non-Goals

- No vector DB.
- No embeddings.
- No RAG.
- No Fable calls.
- No Gemini calls.
- No external news fetching.
- No file upload.
- No file ingestion.
- No NAS scanning.
- No PDF, Word, PowerPoint, image, or video parsing.
- No automatic trading.
- No legacy app integration.

