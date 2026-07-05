from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from phistyle_platform.registry.registry import list_registered_apps
from phistyle_platform.runtime.context import AgentRunContext
from phistyle_platform.runtime.runtime import BrainOrchestrator
from phistyle_platform.runtime.runtime import TriageAgent
from phistyle_platform.runtime.runtime import list_agents, run_agent
from phistyle_platform.runtime.types import UnknownAgentError
from services.llm_router.providers.deepseek import DeepSeekProvider
from services.llm_router.router import resolve_llm_test_route
from services.llm_router.types import LLMRequest, ModelRole
from shared.database.session import get_session
from shared.models.brain_review import BrainReview, BrainReviewConfidence, BrainReviewRecommendation
from shared.models.decision_request import (
    DecisionRequest,
    DecisionRequestRiskLevel,
    DecisionRequestStatus,
    DecisionRequestType,
)
from shared.models.knowledge import (
    AgentMemoryType,
    DecisionLog,
    DecisionStatus,
    KnowledgeDocument,
    KnowledgeSourceType,
    MemoryImportance,
    StorageBackend,
)
from shared.models.human_review import HumanReviewDecision
from shared.models.triage import TriageRecommendation, TriageResult, TriageRiskLevel
from shared.services.brain_review_service import (
    create_brain_review,
    list_brain_reviews,
    list_brain_reviews_for_request,
)
from shared.services.brain_decision_link_service import (
    BrainReviewDecisionLogLinkStaleError,
    BrainReviewDecisionRequestMissingError,
    BrainReviewNotFoundError,
    create_decision_log_draft_from_brain_review,
)
from shared.services.capital_decision_support_service import (
    CapitalDecisionRequestNotFoundError,
    CapitalDecisionRequestScopeError,
    CapitalDecisionRelatedRecordError,
    CapitalDecisionValidationError,
    create_capital_decision_request,
    get_capital_decision_summary,
    list_capital_decision_requests,
    run_capital_decision_pipeline,
)
from shared.services.knowledge_service import (
    create_agent_memory,
    create_decision_log,
    create_knowledge_document,
    list_agent_memory,
    list_decision_logs,
    list_knowledge_documents,
)
from shared.services.human_review_service import (
    DecisionLogNotFoundError,
    DecisionLogNotReviewableError,
    HumanReviewAlreadyExistsError,
    HumanReviewValidationError,
    RelatedDecisionRequestMalformedError,
    RelatedDecisionRequestMissingError,
    list_human_reviews,
    list_human_reviews_for_decision_log,
    review_decision_log,
)
from shared.services.decision_request_service import (
    DecisionRequestStatusTransitionError,
    create_decision_request,
    get_decision_request,
    list_decision_requests,
    update_decision_request_status,
)
from shared.services.triage_service import (
    create_triage_result,
    list_triage_results,
    list_triage_results_for_request,
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


class HumanReviewRequest(BaseModel):
    reviewer: str | None
    review_decision: str | None
    comment: str | None = None

    class Config:
        extra = "forbid"


class HumanReviewDecisionResponse(BaseModel):
    human_review_id: int
    decision_log_id: int
    decision_log_status: str
    decision_request_id: int
    decision_request_status: str
    review_decision: str


class HumanReviewResponse(BaseModel):
    id: int
    decision_log_id: int
    decision_request_id: int
    brain_review_id: int | None
    reviewer: str
    review_decision: HumanReviewDecision
    comment: str | None
    created_at: str


class DecisionRequestCreateRequest(BaseModel):
    app_id: str
    decision_type: DecisionRequestType
    question: str
    context: str
    options: str | None = None
    risk_level: DecisionRequestRiskLevel
    status: DecisionRequestStatus
    created_by: str | None = None
    related_knowledge_document_id: int | None = None
    related_decision_log_id: int | None = None


class DecisionRequestStatusRequest(BaseModel):
    status: DecisionRequestStatus


class DecisionRequestResponse(BaseModel):
    id: int
    app_id: str
    decision_type: DecisionRequestType
    question: str
    context: str
    options: str | None
    risk_level: DecisionRequestRiskLevel
    status: DecisionRequestStatus
    created_by: str | None
    related_knowledge_document_id: int | None
    related_decision_log_id: int | None
    created_at: str
    updated_at: str


class CapitalDecisionCreateRequest(BaseModel):
    question: str | None
    context: str | None
    options: str | None
    risk_level: str
    created_by: str | None

    class Config:
        extra = "forbid"


class CapitalDecisionCreateResponse(BaseModel):
    decision_request_id: int
    app_id: str
    decision_type: str
    status: str


class CapitalDecisionRunResponse(BaseModel):
    decision_request_id: int
    decision_request_status: str
    triage_result_id: int
    triage_recommendation: str
    brain_review_id: int
    brain_recommendation: str
    decision_log_id: int
    decision_log_status: str
    decision_log_approved_by: str | None
    requires_human_review: bool


class CapitalDecisionSummaryResponse(BaseModel):
    decision_request: dict[str, Any]
    triage_result: dict[str, Any] | None
    brain_review: dict[str, Any] | None
    decision_log: dict[str, Any] | None
    human_review: dict[str, Any] | None
    requires_human_review: bool


class TriageRunRequest(BaseModel):
    decision_request_id: int


class TriageOverrideRequest(BaseModel):
    decision_request_id: int
    risk_level: TriageRiskLevel
    recommendation: TriageRecommendation
    rationale: str
    flags: str | None = None
    created_by: str


class TriageResultResponse(BaseModel):
    id: int
    decision_request_id: int
    risk_level: TriageRiskLevel
    recommendation: TriageRecommendation
    rationale: str
    flags: str
    created_by: str
    created_at: str


class BrainRunRequest(BaseModel):
    decision_request_id: int
    triage_result_id: int | None = None


class BrainOverrideRequest(BaseModel):
    decision_request_id: int
    triage_result_id: int | None = None
    recommendation: BrainReviewRecommendation
    rationale: str
    confidence: BrainReviewConfidence
    risks: str | None = None
    required_human_approval: bool = True
    proposed_decision_log_id: int | None = None
    created_by: str


class BrainReviewResponse(BaseModel):
    id: int
    decision_request_id: int
    triage_result_id: int | None
    recommendation: BrainReviewRecommendation
    rationale: str
    confidence: BrainReviewConfidence
    risks: str
    required_human_approval: bool
    llm_backed: bool | None
    llm_provider: str | None
    llm_model: str | None
    llm_fallback_reason: str | None
    llm_floor_applied: bool | None
    proposed_decision_log_id: int | None
    created_by: str
    created_at: str


class DecisionLogDraftRequest(BaseModel):
    proposed_by: str | None = None

    class Config:
        extra = "forbid"


class DecisionLogDraftResponse(BaseModel):
    brain_review_id: int
    decision_log_id: int
    decision_log_status: str
    created: bool


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


@app.get("/capital/decisions", response_model=list[DecisionRequestResponse])
def get_capital_decisions(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_decision_request_response(decision_request) for decision_request in list_capital_decision_requests(session)]


@app.post("/capital/decisions", response_model=CapitalDecisionCreateResponse)
def post_capital_decision(
    request: CapitalDecisionCreateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        decision_request = create_capital_decision_request(
            session,
            question=request.question,
            context=request.context,
            options=request.options,
            risk_level=request.risk_level,
            created_by=request.created_by,
        )
    except CapitalDecisionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "decision_request_id": decision_request.id,
        "app_id": decision_request.app_id,
        "decision_type": decision_request.decision_type.value,
        "status": decision_request.status.value,
    }


@app.post("/capital/decisions/{decision_request_id}/run", response_model=CapitalDecisionRunResponse)
def post_capital_decision_run(
    decision_request_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = run_capital_decision_pipeline(session, decision_request_id=decision_request_id)
    except CapitalDecisionRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        CapitalDecisionRequestScopeError,
        CapitalDecisionRelatedRecordError,
        BrainReviewDecisionLogLinkStaleError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "decision_request_id": result.decision_request_id,
        "decision_request_status": result.decision_request_status,
        "triage_result_id": result.triage_result_id,
        "triage_recommendation": result.triage_recommendation,
        "brain_review_id": result.brain_review_id,
        "brain_recommendation": result.brain_recommendation,
        "decision_log_id": result.decision_log_id,
        "decision_log_status": result.decision_log_status,
        "decision_log_approved_by": result.decision_log_approved_by,
        "requires_human_review": result.requires_human_review,
    }


@app.get("/capital/decisions/{decision_request_id}", response_model=CapitalDecisionSummaryResponse)
def get_capital_decision(
    decision_request_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        summary = get_capital_decision_summary(session, decision_request_id=decision_request_id)
    except CapitalDecisionRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CapitalDecisionRequestScopeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CapitalDecisionRelatedRecordError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _capital_decision_summary_response(summary)


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


@app.get("/decisions/human-reviews", response_model=list[HumanReviewResponse])
def get_human_reviews(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_human_review_response(review) for review in list_human_reviews(session)]


@app.get("/decisions/decision-logs/{decision_log_id}/human-reviews", response_model=list[HumanReviewResponse])
def get_human_reviews_for_decision_log(
    decision_log_id: int,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [
        _human_review_response(review)
        for review in list_human_reviews_for_decision_log(session, decision_log_id)
    ]


@app.post(
    "/decisions/decision-logs/{decision_log_id}/human-review",
    response_model=HumanReviewDecisionResponse,
)
def post_human_review(
    decision_log_id: int,
    request: HumanReviewRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = review_decision_log(
            session,
            decision_log_id=decision_log_id,
            reviewer=request.reviewer,
            review_decision=request.review_decision,
            comment=request.comment,
        )
    except DecisionLogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RelatedDecisionRequestMissingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        HumanReviewValidationError,
        RelatedDecisionRequestMalformedError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (
        DecisionLogNotReviewableError,
        HumanReviewAlreadyExistsError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "human_review_id": result.human_review_id,
        "decision_log_id": result.decision_log_id,
        "decision_log_status": result.decision_log_status,
        "decision_request_id": result.decision_request_id,
        "decision_request_status": result.decision_request_status,
        "review_decision": result.review_decision,
    }


@app.get("/decisions/requests", response_model=list[DecisionRequestResponse])
def get_decision_requests(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_decision_request_response(decision_request) for decision_request in list_decision_requests(session)]


@app.post("/decisions/requests", response_model=DecisionRequestResponse)
def post_decision_request(
    request: DecisionRequestCreateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        decision_request = create_decision_request(
            session,
            app_id=request.app_id,
            decision_type=request.decision_type.value,
            question=request.question,
            context=request.context,
            options=request.options,
            risk_level=request.risk_level.value,
            status=request.status.value,
            created_by=request.created_by,
            related_knowledge_document_id=request.related_knowledge_document_id,
            related_decision_log_id=request.related_decision_log_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Foreign key constraint failed") from exc
    return _decision_request_response(decision_request)


@app.get("/decisions/requests/{decision_request_id}", response_model=DecisionRequestResponse)
def get_decision_request_endpoint(
    decision_request_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    decision_request = get_decision_request(session, decision_request_id)
    if decision_request is None:
        raise HTTPException(status_code=404, detail=f"Unknown decision_request_id: {decision_request_id}")
    return _decision_request_response(decision_request)


@app.patch("/decisions/requests/{decision_request_id}/status", response_model=DecisionRequestResponse)
def patch_decision_request_status(
    decision_request_id: int,
    request: DecisionRequestStatusRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        decision_request = update_decision_request_status(
            session,
            decision_request_id=decision_request_id,
            status=request.status.value,
        )
    except DecisionRequestStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if decision_request is None:
        raise HTTPException(status_code=404, detail=f"Unknown decision_request_id: {decision_request_id}")
    return _decision_request_response(decision_request)


@app.get("/decisions/triage", response_model=list[TriageResultResponse])
def get_triage_results(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_triage_result_response(result) for result in list_triage_results(session)]


@app.get("/decisions/requests/{decision_request_id}/triage", response_model=list[TriageResultResponse])
def get_triage_results_for_decision_request(
    decision_request_id: int,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    decision_request = get_decision_request(session, decision_request_id)
    if decision_request is None:
        raise HTTPException(status_code=404, detail=f"Unknown decision_request_id: {decision_request_id}")
    return [
        _triage_result_response(result)
        for result in list_triage_results_for_request(session, decision_request_id)
    ]


@app.post("/decisions/triage/run", response_model=TriageResultResponse)
def post_triage_run(
    request: TriageRunRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    decision_request = get_decision_request(session, request.decision_request_id)
    if decision_request is None:
        raise HTTPException(status_code=404, detail=f"Unknown decision_request_id: {request.decision_request_id}")

    result = TriageAgent().run(
        {
            "decision_request_id": decision_request.id,
            "question": decision_request.question,
            "context": decision_request.context,
            "decision_type": decision_request.decision_type.value,
            "risk_level": decision_request.risk_level.value,
        },
        AgentRunContext(run_id=f"triage-{decision_request.id}"),
    )
    try:
        triage_result = create_triage_result(
            session,
            decision_request_id=decision_request.id,
            risk_level=result.output["risk_level"],
            recommendation=result.output["recommendation"],
            rationale=result.output["rationale"],
            flags=result.output["flags"],
            created_by="triage-agent",
        )
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Foreign key constraint failed") from exc
    return _triage_result_response(triage_result)


@app.post("/decisions/triage/override", response_model=TriageResultResponse)
def post_triage_override(
    request: TriageOverrideRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if request.created_by == "triage-agent":
        raise HTTPException(status_code=422, detail="created_by='triage-agent' is reserved for system-run triage")
    if get_decision_request(session, request.decision_request_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown decision_request_id: {request.decision_request_id}")
    try:
        triage_result = create_triage_result(
            session,
            decision_request_id=request.decision_request_id,
            risk_level=request.risk_level.value,
            recommendation=request.recommendation.value,
            rationale=request.rationale,
            flags=request.flags,
            created_by=request.created_by,
        )
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Foreign key constraint failed") from exc
    return _triage_result_response(triage_result)


@app.get("/decisions/brain-reviews", response_model=list[BrainReviewResponse])
def get_brain_reviews(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_brain_review_response(review) for review in list_brain_reviews(session)]


@app.get("/decisions/requests/{decision_request_id}/brain-reviews", response_model=list[BrainReviewResponse])
def get_brain_reviews_for_decision_request(
    decision_request_id: int,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    decision_request = get_decision_request(session, decision_request_id)
    if decision_request is None:
        raise HTTPException(status_code=404, detail=f"Unknown decision_request_id: {decision_request_id}")
    return [_brain_review_response(review) for review in list_brain_reviews_for_request(session, decision_request_id)]


@app.post("/decisions/brain/run", response_model=BrainReviewResponse)
def post_brain_run(
    request: BrainRunRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    decision_request = get_decision_request(session, request.decision_request_id)
    if decision_request is None:
        raise HTTPException(status_code=404, detail=f"Unknown decision_request_id: {request.decision_request_id}")

    triage_result = session.get(TriageResult, request.triage_result_id) if request.triage_result_id else None
    triage_recommendation = triage_result.recommendation.value if triage_result else None
    triage_result_id = triage_result.id if triage_result else None
    result = BrainOrchestrator().run(
        {
            "decision_request_id": decision_request.id,
            "triage_result_id": triage_result_id,
            "question": decision_request.question,
            "context": decision_request.context,
            "risk_level": decision_request.risk_level.value,
            "triage_recommendation": triage_recommendation,
        },
        AgentRunContext(run_id=f"brain-{decision_request.id}"),
    )
    try:
        brain_review = create_brain_review(
            session,
            decision_request_id=decision_request.id,
            triage_result_id=result.output["triage_result_id"],
            recommendation=result.output["recommendation"],
            rationale=result.output["rationale"],
            confidence=result.output["confidence"],
            risks=result.output["risks"],
            required_human_approval=result.output["required_human_approval"],
            proposed_decision_log_id=None,
            llm_backed=result.output["llm_backed"],
            llm_provider=result.output["llm_provider"],
            llm_model=result.output["llm_model"],
            llm_fallback_reason=result.output["llm_fallback_reason"],
            llm_floor_applied=result.output["llm_floor_applied"],
            created_by="brain-orchestrator",
        )
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Foreign key constraint failed") from exc
    return _brain_review_response(brain_review)


@app.post("/decisions/brain/override", response_model=BrainReviewResponse)
def post_brain_override(
    request: BrainOverrideRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if request.created_by == "brain-orchestrator":
        raise HTTPException(status_code=422, detail="created_by='brain-orchestrator' is reserved for system-run reviews")
    if get_decision_request(session, request.decision_request_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown decision_request_id: {request.decision_request_id}")
    if request.triage_result_id is not None and session.get(TriageResult, request.triage_result_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown triage_result_id: {request.triage_result_id}")
    if request.proposed_decision_log_id is not None and session.get(DecisionLog, request.proposed_decision_log_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown proposed_decision_log_id: {request.proposed_decision_log_id}")
    try:
        brain_review = create_brain_review(
            session,
            decision_request_id=request.decision_request_id,
            triage_result_id=request.triage_result_id,
            recommendation=request.recommendation.value,
            rationale=request.rationale,
            confidence=request.confidence.value,
            risks=request.risks,
            required_human_approval=request.required_human_approval,
            proposed_decision_log_id=request.proposed_decision_log_id,
            created_by=request.created_by,
        )
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Foreign key constraint failed") from exc
    return _brain_review_response(brain_review)


@app.post(
    "/decisions/brain-reviews/{brain_review_id}/decision-log-draft",
    response_model=DecisionLogDraftResponse,
)
def post_brain_review_decision_log_draft(
    brain_review_id: int,
    request: DecisionLogDraftRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = create_decision_log_draft_from_brain_review(
            session,
            brain_review_id=brain_review_id,
            proposed_by=request.proposed_by,
        )
    except BrainReviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BrainReviewDecisionRequestMissingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BrainReviewDecisionLogLinkStaleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "brain_review_id": result.brain_review_id,
        "decision_log_id": result.decision_log_id,
        "decision_log_status": result.decision_log_status,
        "created": result.created,
    }


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


def _capital_decision_summary_response(summary) -> dict[str, Any]:
    decision_request = summary.decision_request
    triage_result = summary.triage_result
    brain_review = summary.brain_review
    decision_log = summary.decision_log
    human_review = summary.human_review
    return {
        "decision_request": {
            "id": decision_request.id,
            "question": decision_request.question,
            "context": decision_request.context,
            "options": decision_request.options,
            "risk_level": decision_request.risk_level.value,
            "status": decision_request.status.value,
        },
        "triage_result": None
        if triage_result is None
        else {
            "id": triage_result.id,
            "recommendation": triage_result.recommendation.value,
        },
        "brain_review": None
        if brain_review is None
        else {
            "id": brain_review.id,
            "recommendation": brain_review.recommendation.value,
            "confidence": brain_review.confidence.value,
            "llm_backed": brain_review.llm_backed,
            "llm_provider": brain_review.llm_provider,
            "llm_model": brain_review.llm_model,
            "llm_fallback_reason": brain_review.llm_fallback_reason,
            "llm_floor_applied": brain_review.llm_floor_applied,
        },
        "decision_log": None
        if decision_log is None
        else {
            "id": decision_log.id,
            "status": decision_log.status.value,
            "approved_by": decision_log.approved_by,
        },
        "human_review": None
        if human_review is None
        else {
            "id": human_review.id,
            "reviewer": human_review.reviewer,
            "review_decision": human_review.review_decision.value,
        },
        "requires_human_review": summary.requires_human_review,
    }


def _human_review_response(human_review) -> dict[str, Any]:
    return {
        "id": human_review.id,
        "decision_log_id": human_review.decision_log_id,
        "decision_request_id": human_review.decision_request_id,
        "brain_review_id": human_review.brain_review_id,
        "reviewer": human_review.reviewer,
        "review_decision": human_review.review_decision,
        "comment": human_review.comment,
        "created_at": human_review.created_at.isoformat(),
    }


def _decision_request_response(decision_request: DecisionRequest) -> dict[str, Any]:
    return {
        "id": decision_request.id,
        "app_id": decision_request.app_id,
        "decision_type": decision_request.decision_type,
        "question": decision_request.question,
        "context": decision_request.context,
        "options": decision_request.options,
        "risk_level": decision_request.risk_level,
        "status": decision_request.status,
        "created_by": decision_request.created_by,
        "related_knowledge_document_id": decision_request.related_knowledge_document_id,
        "related_decision_log_id": decision_request.related_decision_log_id,
        "created_at": decision_request.created_at.isoformat(),
        "updated_at": decision_request.updated_at.isoformat(),
    }


def _triage_result_response(triage_result: TriageResult) -> dict[str, Any]:
    return {
        "id": triage_result.id,
        "decision_request_id": triage_result.decision_request_id,
        "risk_level": triage_result.risk_level,
        "recommendation": triage_result.recommendation,
        "rationale": triage_result.rationale,
        "flags": triage_result.flags or "",
        "created_by": triage_result.created_by,
        "created_at": triage_result.created_at.isoformat(),
    }


def _brain_review_response(brain_review: BrainReview) -> dict[str, Any]:
    return {
        "id": brain_review.id,
        "decision_request_id": brain_review.decision_request_id,
        "triage_result_id": brain_review.triage_result_id,
        "recommendation": brain_review.recommendation,
        "rationale": brain_review.rationale,
        "confidence": brain_review.confidence,
        "risks": brain_review.risks or "",
        "required_human_approval": brain_review.required_human_approval,
        "llm_backed": brain_review.llm_backed,
        "llm_provider": brain_review.llm_provider,
        "llm_model": brain_review.llm_model,
        "llm_fallback_reason": brain_review.llm_fallback_reason,
        "llm_floor_applied": brain_review.llm_floor_applied,
        "proposed_decision_log_id": brain_review.proposed_decision_log_id,
        "created_by": brain_review.created_by,
        "created_at": brain_review.created_at.isoformat(),
    }
