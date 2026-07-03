from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from sqlalchemy.orm import Session

from phistyle_platform.registry.registry import list_registered_apps
from phistyle_platform.runtime.runtime import list_agents, run_agent
from phistyle_platform.runtime.types import UnknownAgentError
from services.llm_router.providers.deepseek import DeepSeekProvider
from services.llm_router.router import resolve_llm_test_route
from services.llm_router.types import LLMRequest, ModelRole
from shared.database.session import get_session
from shared.models.knowledge import (
    AgentMemoryType,
    DecisionLog,
    DecisionStatus,
    KnowledgeDocument,
    KnowledgeSourceType,
    MemoryImportance,
    StorageBackend,
)
from shared.services.knowledge_service import (
    create_agent_memory,
    create_decision_log,
    create_knowledge_document,
    list_agent_memory,
    list_decision_logs,
    list_knowledge_documents,
)


app = FastAPI(title="PhiStyle OS API")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRunRequest(BaseModel):
    agent_id: str
    input: dict[str, Any]


class LLMTestRequest(BaseModel):
    role: str
    prompt: str


class KnowledgeDocumentRequest(BaseModel):
    title: str
    content: str
    source_type: KnowledgeSourceType
    tags: str | None = None
    storage_backend: StorageBackend
    file_path: str | None = None


class KnowledgeDocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    source_type: KnowledgeSourceType
    tags: str | None
    storage_backend: StorageBackend
    file_path: str | None
    created_at: str
    updated_at: str


class AgentMemoryRequest(BaseModel):
    agent_id: str
    memory_type: AgentMemoryType
    content: str
    importance: MemoryImportance


class AgentMemoryResponse(BaseModel):
    id: int
    agent_id: str
    memory_type: AgentMemoryType
    content: str
    importance: MemoryImportance
    created_at: str


class DecisionLogRequest(BaseModel):
    title: str
    decision: str
    rationale: str
    proposed_by: str | None = None
    reviewed_by: str | None = None
    approved_by: str | None = None
    status: DecisionStatus
    related_request_id: str | None = None


class DecisionLogResponse(BaseModel):
    id: int
    title: str
    decision: str
    rationale: str
    proposed_by: str | None
    reviewed_by: str | None
    approved_by: str | None
    status: DecisionStatus
    related_request_id: str | None
    created_at: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/apps")
def apps() -> list[dict[str, str]]:
    return list_registered_apps()


@app.get("/agents")
def agents() -> list[dict[str, str]]:
    return list_agents()


@app.post("/agents/run")
def run_agent_endpoint(request: AgentRunRequest) -> dict[str, Any]:
    try:
        result = run_agent(request.agent_id, request.input)
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "agent_id": result.agent_id,
        "status": result.status,
        "output": result.output,
    }


@app.get("/knowledge/documents", response_model=list[KnowledgeDocumentResponse])
def get_knowledge_documents(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_knowledge_document_response(document) for document in list_knowledge_documents(session)]


@app.post("/knowledge/documents", response_model=KnowledgeDocumentResponse)
def post_knowledge_document(
    request: KnowledgeDocumentRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    document = create_knowledge_document(
        session,
        title=request.title,
        content=request.content,
        source_type=request.source_type.value,
        tags=request.tags,
        storage_backend=request.storage_backend.value,
        file_path=request.file_path,
    )
    return _knowledge_document_response(document)


@app.get("/knowledge/memories", response_model=list[AgentMemoryResponse])
def get_knowledge_memories(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_agent_memory_response(memory) for memory in list_agent_memory(session)]


@app.post("/knowledge/memories", response_model=AgentMemoryResponse)
def post_knowledge_memory(
    request: AgentMemoryRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    memory = create_agent_memory(
        session,
        agent_id=request.agent_id,
        memory_type=request.memory_type.value,
        content=request.content,
        importance=request.importance.value,
    )
    return _agent_memory_response(memory)


@app.get("/knowledge/decisions", response_model=list[DecisionLogResponse])
def get_knowledge_decisions(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_decision_log_response(decision) for decision in list_decision_logs(session)]


@app.post("/knowledge/decisions", response_model=DecisionLogResponse)
def post_knowledge_decision(
    request: DecisionLogRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    decision_log = create_decision_log(
        session,
        title=request.title,
        decision=request.decision,
        rationale=request.rationale,
        proposed_by=request.proposed_by,
        reviewed_by=request.reviewed_by,
        approved_by=request.approved_by,
        status=request.status.value,
        related_request_id=request.related_request_id,
    )
    return _decision_log_response(decision_log)


@app.post("/llm/test")
def llm_test_endpoint(request: LLMTestRequest) -> dict[str, Any]:
    try:
        role, provider_id = resolve_llm_test_route(request.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if provider_id == "fable":
        return {
            "provider_id": "fable",
            "model": "fable-5",
            "dry_run": True,
            "content": f"[dry-run:fable] {request.prompt}",
            "metadata": {
                "role": role.value,
                "reason": "Fable is scaffolded but not enabled for real calls in Phase 6C",
            },
        }
    if provider_id != "deepseek":
        raise HTTPException(status_code=400, detail=f"Unsupported provider route: {provider_id}")
    response = DeepSeekProvider().chat(LLMRequest(role=role, prompt=request.prompt))
    return {
        "provider_id": response.provider_id,
        "model": response.model,
        "dry_run": response.dry_run,
        "content": response.content,
        "metadata": response.metadata,
    }


def _knowledge_document_response(document: KnowledgeDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "title": document.title,
        "content": document.content,
        "source_type": document.source_type,
        "tags": document.tags,
        "storage_backend": document.storage_backend,
        "file_path": document.file_path,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }


def _agent_memory_response(memory) -> dict[str, Any]:
    return {
        "id": memory.id,
        "agent_id": memory.agent_id,
        "memory_type": memory.memory_type,
        "content": memory.content,
        "importance": memory.importance,
        "created_at": memory.created_at.isoformat(),
    }


def _decision_log_response(decision_log: DecisionLog) -> dict[str, Any]:
    return {
        "id": decision_log.id,
        "title": decision_log.title,
        "decision": decision_log.decision,
        "rationale": decision_log.rationale,
        "proposed_by": decision_log.proposed_by,
        "reviewed_by": decision_log.reviewed_by,
        "approved_by": decision_log.approved_by,
        "status": decision_log.status,
        "related_request_id": decision_log.related_request_id,
        "created_at": decision_log.created_at.isoformat(),
    }
