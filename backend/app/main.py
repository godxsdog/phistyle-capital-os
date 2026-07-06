from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
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
from shared.services.point_wallet_service import (
    PointWalletError,
    PointWalletNotFoundError,
    add_award_availability,
    add_point_balance,
    add_valuation_rate,
    create_award_watch,
    create_loyalty_program,
    create_transfer_partner,
    get_portfolio_summary,
    list_award_availability,
    list_award_watches,
    list_loyalty_programs,
    list_point_balances,
    list_transfer_partners,
    list_valuation_rates,
    seed_default_valuation_programs,
)
from shared.services.seats_aero_service import SeatsAeroError, fetch_award_watch
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
from shared.services.trade_attribution_service import get_trade_attribution_metrics
from shared.services.trade_import_service import (
    TradeImportError,
    UnsupportedTradeImportSourceError,
    import_trade_history,
    list_cash_transactions,
    list_import_batches,
    list_realized_trades,
    list_trade_fills,
    warnings_for_batch,
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


class TradeImportResponse(BaseModel):
    batch_id: int
    source: str
    created: bool
    fill_count: int
    cash_row_count: int
    warning_count: int
    warnings: list[str]


class ImportBatchResponse(BaseModel):
    id: int
    source: str
    content_hash: str
    imported_at: str
    fill_count: int
    cash_row_count: int
    warning_count: int
    warnings: list[str]


class TradeFillResponse(BaseModel):
    id: int
    import_batch_id: int
    executed_at_raw: str
    executed_at: str | None
    symbol: str
    side: str
    quantity: str
    position_effect: str
    instrument_type: str | None
    price: str
    net_price: str | None
    order_type: str | None
    currency: str


class CashTransactionResponse(BaseModel):
    id: int
    import_batch_id: int
    txn_date: str
    txn_time: str | None
    ref_no: str | None
    description: str
    misc_fees: str | None
    commissions_fees: str | None
    amount: str | None
    currency: str


class RealizedTradeResponse(BaseModel):
    id: int
    import_batch_id: int
    symbol: str
    direction: str
    opened_at: str | None
    closed_at: str | None
    quantity: str
    avg_entry: str
    avg_exit: str
    gross_pnl: str
    currency: str
    holding_period_seconds: int | None


class TradeAttributionResponse(BaseModel):
    trade_count: int
    gross_pnl: str
    win_rate: float
    expectancy: str
    max_consecutive_losses: int
    by_symbol: list[dict[str, Any]]
    by_direction: list[dict[str, Any]]
    by_instrument_type: list[dict[str, Any]]
    by_holding_period: list[dict[str, Any]]
    by_entry_weekday: list[dict[str, Any]]
    by_entry_hour: list[dict[str, Any]]
    averaging_down: list[dict[str, Any]]
    leveraged_symbols: list[str]
    narrative: dict[str, Any]


class LoyaltyProgramRequest(BaseModel):
    name: str
    kind: str
    notes: str | None = None


class LoyaltyProgramResponse(BaseModel):
    id: int
    name: str
    kind: str
    notes: str | None


class PointBalanceRequest(BaseModel):
    program_id: int
    balance: Decimal
    as_of: date
    expires_at: date | None = None
    note: str | None = None


class PointBalanceResponse(BaseModel):
    id: int
    program_id: int
    balance: str
    as_of: str
    expires_at: str | None
    note: str | None
    created_at: str | None


class ValuationRateRequest(BaseModel):
    program_id: int
    twd_per_point: Decimal
    effective_date: date
    source: str | None = None


class ValuationRateResponse(BaseModel):
    id: int
    program_id: int
    twd_per_point: str
    effective_date: str
    source: str | None


class TransferPartnerRequest(BaseModel):
    from_program_id: int
    to_program_id: int
    ratio_from: int
    ratio_to: int
    transfer_days: str | None = None
    notes: str | None = None


class TransferPartnerResponse(BaseModel):
    id: int
    from_program_id: int
    to_program_id: int
    ratio_from: int
    ratio_to: int
    transfer_days: str | None
    notes: str | None


class AwardWatchRequest(BaseModel):
    origin: str
    destination: str
    cabin: str
    program_id: int | None = None
    active: bool = True


class AwardWatchResponse(BaseModel):
    id: int
    origin: str
    destination: str
    cabin: str
    program_id: int | None
    active: bool


class AwardAvailabilityRequest(BaseModel):
    watch_id: int
    seen_date: date
    flight_date: date
    program: str
    seats: int | None = None
    miles_cost: Decimal | None = None
    taxes_fees: str | None = None
    source: str = "manual"
    raw: str | None = None


class AwardAvailabilityResponse(BaseModel):
    id: int
    watch_id: int
    seen_date: str
    flight_date: str
    program: str
    seats: int | None
    miles_cost: str | None
    taxes_fees: str | None
    source: str
    raw: str | None


class AwardFetchResponse(BaseModel):
    created: int


class PointPortfolioResponse(BaseModel):
    total_value_twd: str
    programs: list[dict[str, Any]]
    expiring_soon: list[dict[str, Any]]


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


@app.post("/capital/trade-imports", response_model=TradeImportResponse)
async def post_capital_trade_import(
    source: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    file_bytes = await file.read()
    try:
        result = import_trade_history(session, source=source, file_bytes=file_bytes)
    except UnsupportedTradeImportSourceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TradeImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    batch = result.batch
    return {
        "batch_id": batch.id,
        "source": batch.source,
        "created": result.created,
        "fill_count": batch.fill_count,
        "cash_row_count": batch.cash_row_count,
        "warning_count": batch.warning_count,
        "warnings": result.warnings,
    }


@app.get("/capital/trade-imports", response_model=list[ImportBatchResponse])
def get_capital_trade_imports(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_import_batch_response(batch) for batch in list_import_batches(session)]


@app.get("/capital/trade-fills", response_model=list[TradeFillResponse])
def get_capital_trade_fills(
    import_batch_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [_trade_fill_response(fill) for fill in list_trade_fills(session, import_batch_id)]


@app.get("/capital/cash-transactions", response_model=list[CashTransactionResponse])
def get_capital_cash_transactions(
    import_batch_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [_cash_transaction_response(txn) for txn in list_cash_transactions(session, import_batch_id)]


@app.get("/capital/realized-trades", response_model=list[RealizedTradeResponse])
def get_capital_realized_trades(
    import_batch_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [_realized_trade_response(trade) for trade in list_realized_trades(session, import_batch_id)]


@app.get("/capital/trade-attribution", response_model=TradeAttributionResponse)
def get_capital_trade_attribution(session: Session = Depends(get_session)) -> dict[str, Any]:
    return get_trade_attribution_metrics(session)


@app.post("/wallet/seed-defaults")
def post_wallet_seed_defaults(session: Session = Depends(get_session)) -> dict[str, str]:
    seed_default_valuation_programs(session)
    return {"status": "ok"}


@app.get("/wallet/programs", response_model=list[LoyaltyProgramResponse])
def get_wallet_programs(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_loyalty_program_response(program) for program in list_loyalty_programs(session)]


@app.post("/wallet/programs", response_model=LoyaltyProgramResponse)
def post_wallet_program(
    request: LoyaltyProgramRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        program = create_loyalty_program(session, name=request.name, kind=request.kind, notes=request.notes)
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Program already exists") from exc
    return _loyalty_program_response(program)


@app.get("/wallet/balances", response_model=list[PointBalanceResponse])
def get_wallet_balances(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_point_balance_response(row) for row in list_point_balances(session)]


@app.post("/wallet/balances", response_model=PointBalanceResponse)
def post_wallet_balance(
    request: PointBalanceRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = add_point_balance(
            session,
            program_id=request.program_id,
            balance=request.balance,
            as_of=request.as_of,
            expires_at=request.expires_at,
            note=request.note,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _point_balance_response(row)


@app.get("/wallet/valuations", response_model=list[ValuationRateResponse])
def get_wallet_valuations(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_valuation_rate_response(row) for row in list_valuation_rates(session)]


@app.post("/wallet/valuations", response_model=ValuationRateResponse)
def post_wallet_valuation(
    request: ValuationRateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = add_valuation_rate(
            session,
            program_id=request.program_id,
            twd_per_point=request.twd_per_point,
            effective_date=request.effective_date,
            source=request.source,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Valuation already exists for program/effective_date") from exc
    return _valuation_rate_response(row)


@app.get("/wallet/transfers", response_model=list[TransferPartnerResponse])
def get_wallet_transfers(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_transfer_partner_response(row) for row in list_transfer_partners(session)]


@app.post("/wallet/transfers", response_model=TransferPartnerResponse)
def post_wallet_transfer(
    request: TransferPartnerRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_transfer_partner(
            session,
            from_program_id=request.from_program_id,
            to_program_id=request.to_program_id,
            ratio_from=request.ratio_from,
            ratio_to=request.ratio_to,
            transfer_days=request.transfer_days,
            notes=request.notes,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Transfer partner already exists") from exc
    return _transfer_partner_response(row)


@app.get("/wallet/watches", response_model=list[AwardWatchResponse])
def get_wallet_watches(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_award_watch_response(row) for row in list_award_watches(session)]


@app.post("/wallet/watches", response_model=AwardWatchResponse)
def post_wallet_watch(
    request: AwardWatchRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_award_watch(
            session,
            origin=request.origin,
            destination=request.destination,
            cabin=request.cabin,
            program_id=request.program_id,
            active=request.active,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _award_watch_response(row)


@app.get("/wallet/availability", response_model=list[AwardAvailabilityResponse])
def get_wallet_availability(
    watch_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [_award_availability_response(row) for row in list_award_availability(session, watch_id)]


@app.post("/wallet/availability", response_model=AwardAvailabilityResponse)
def post_wallet_availability(
    request: AwardAvailabilityRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = add_award_availability(
            session,
            watch_id=request.watch_id,
            seen_date=request.seen_date,
            flight_date=request.flight_date,
            program=request.program,
            seats=request.seats,
            miles_cost=request.miles_cost,
            taxes_fees=request.taxes_fees,
            source=request.source,
            raw=request.raw,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Award availability already exists") from exc
    return _award_availability_response(row)


@app.post("/wallet/watches/{watch_id}/fetch", response_model=AwardFetchResponse)
def post_wallet_watch_fetch(
    watch_id: int,
    session: Session = Depends(get_session),
) -> dict[str, int]:
    try:
        return fetch_award_watch(session, watch_id=watch_id)
    except SeatsAeroError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/wallet/portfolio", response_model=PointPortfolioResponse)
def get_wallet_portfolio(session: Session = Depends(get_session)) -> dict[str, Any]:
    return _point_portfolio_response(get_portfolio_summary(session))


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


def _import_batch_response(batch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "source": batch.source,
        "content_hash": batch.content_hash,
        "imported_at": batch.imported_at.isoformat(),
        "fill_count": batch.fill_count,
        "cash_row_count": batch.cash_row_count,
        "warning_count": batch.warning_count,
        "warnings": warnings_for_batch(batch),
    }


def _trade_fill_response(fill) -> dict[str, Any]:
    return {
        "id": fill.id,
        "import_batch_id": fill.import_batch_id,
        "executed_at_raw": fill.executed_at_raw,
        "executed_at": fill.executed_at.isoformat() if fill.executed_at is not None else None,
        "symbol": fill.symbol,
        "side": fill.side,
        "quantity": str(fill.quantity),
        "position_effect": fill.position_effect,
        "instrument_type": fill.instrument_type,
        "price": str(fill.price),
        "net_price": str(fill.net_price) if fill.net_price is not None else None,
        "order_type": fill.order_type,
        "currency": fill.currency,
    }


def _cash_transaction_response(txn) -> dict[str, Any]:
    return {
        "id": txn.id,
        "import_batch_id": txn.import_batch_id,
        "txn_date": txn.txn_date.isoformat(),
        "txn_time": txn.txn_time,
        "ref_no": txn.ref_no,
        "description": txn.description,
        "misc_fees": str(txn.misc_fees) if txn.misc_fees is not None else None,
        "commissions_fees": str(txn.commissions_fees) if txn.commissions_fees is not None else None,
        "amount": str(txn.amount) if txn.amount is not None else None,
        "currency": txn.currency,
    }


def _realized_trade_response(trade) -> dict[str, Any]:
    return {
        "id": trade.id,
        "import_batch_id": trade.import_batch_id,
        "symbol": trade.symbol,
        "direction": trade.direction,
        "opened_at": trade.opened_at.isoformat() if trade.opened_at is not None else None,
        "closed_at": trade.closed_at.isoformat() if trade.closed_at is not None else None,
        "quantity": str(trade.quantity),
        "avg_entry": str(trade.avg_entry),
        "avg_exit": str(trade.avg_exit),
        "gross_pnl": str(trade.gross_pnl),
        "currency": trade.currency,
        "holding_period_seconds": trade.holding_period_seconds,
    }


def _loyalty_program_response(program) -> dict[str, Any]:
    return {"id": program.id, "name": program.name, "kind": program.kind, "notes": program.notes}


def _point_balance_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "program_id": row.program_id,
        "balance": str(row.balance),
        "as_of": row.as_of.isoformat(),
        "expires_at": row.expires_at.isoformat() if row.expires_at is not None else None,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at is not None else None,
    }


def _valuation_rate_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "program_id": row.program_id,
        "twd_per_point": str(row.twd_per_point),
        "effective_date": row.effective_date.isoformat(),
        "source": row.source,
    }


def _transfer_partner_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "from_program_id": row.from_program_id,
        "to_program_id": row.to_program_id,
        "ratio_from": row.ratio_from,
        "ratio_to": row.ratio_to,
        "transfer_days": row.transfer_days,
        "notes": row.notes,
    }


def _award_watch_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "origin": row.origin,
        "destination": row.destination,
        "cabin": row.cabin,
        "program_id": row.program_id,
        "active": row.active,
    }


def _award_availability_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "watch_id": row.watch_id,
        "seen_date": row.seen_date.isoformat(),
        "flight_date": row.flight_date.isoformat(),
        "program": row.program,
        "seats": row.seats,
        "miles_cost": str(row.miles_cost) if row.miles_cost is not None else None,
        "taxes_fees": row.taxes_fees,
        "source": row.source,
        "raw": row.raw,
    }


def _point_portfolio_response(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_value_twd": str(summary["total_value_twd"]),
        "programs": [_portfolio_row_response(row) for row in summary["programs"]],
        "expiring_soon": [_portfolio_row_response(row) for row in summary["expiring_soon"]],
    }


def _portfolio_row_response(row) -> dict[str, Any]:
    return {
        "program_id": row.program_id,
        "program_name": row.program_name,
        "balance": str(row.balance),
        "as_of": row.as_of.isoformat(),
        "expires_at": row.expires_at.isoformat() if row.expires_at is not None else None,
        "twd_per_point": str(row.twd_per_point) if row.twd_per_point is not None else None,
        "value_twd": str(row.value_twd) if row.value_twd is not None else None,
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
