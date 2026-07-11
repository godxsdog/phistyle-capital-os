from __future__ import annotations

import json
from datetime import date, datetime, timezone, timedelta
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
from shared.models.point_wallet import AwardSnapshot, AwardWatch, ExpiryAlert, HotelVoucher, PointProgram, QuestResult, TransferRule, TripQuest
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
from shared.services.hotel_compare_service import (
    create_hotel_stay_quote,
    evaluate_hotel_stay_quote,
    list_hotel_stay_quotes,
)
from shared.services.exchange_rate_service import list_fx_rates, refresh_fx_rates
from shared.services.award_cost_engine import (
    create_award_quote,
    evaluate_award_quote,
    get_award_quote,
    list_award_quotes,
    list_funding_scenarios,
)
from shared.services.backtest_service import (
    BacktestError,
    get_backtest_run,
    list_backtest_runs,
    list_strategy_specs,
    run_backtest,
)
from shared.services.point_wallet_service import (
    PointWalletError,
    PointWalletNotFoundError,
    PointWalletStateError,
    create_account,
    create_hotel_voucher,
    create_ledger_transaction,
    create_program,
    create_purchase_offer,
    create_transfer_rule,
    get_portfolio_summary,
    list_accounts,
    list_cost_lots,
    list_hotel_vouchers,
    list_ledger_transactions,
    list_programs,
    list_purchase_offers,
    list_transfer_rules,
    update_hotel_voucher_status,
)
from shared.services.seats_aero_service import (
    SeatsAeroError,
    create_award_watch,
    delete_award_watch,
    fetch_award_watch,
    list_award_snapshots,
    list_award_watches,
    list_expiry_alerts,
    promote_snapshot_to_award_quote,
    scan_expiry_alerts,
    update_award_watch,
)
from shared.services.trip_quest_service import (
    TripQuestError,
    get_trip_quest,
    list_quest_results,
    list_trip_quests,
    run_trip_quest,
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
from shared.services.market_data_service import (
    MarketDataError,
    create_watchlist_symbol,
    delete_watchlist_symbol,
    ingest_taifex,
    ingest_yahoo_us,
    list_ingest_runs,
    list_watchlist_symbols,
    market_sanity_summary,
    update_watchlist_symbol,
)
from shared.services.trade_plan_service import (
    TradePlanError,
    TradePlanNotFoundError,
    TradePlanOutcomeExistsError,
    close_trade_plan,
    create_trade_plan,
    list_trade_plans,
    mark_open_trade_plans,
    trade_plan_stats,
)
from shared.services.tool_monitor_service import (
    ToolMonitorError,
    get_or_create_flight_watch_settings,
    query_flight_status,
    parse_last_status as parse_tool_monitor_status,
    tick_flight_watch,
    update_flight_watch_settings,
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


class MarketWatchlistRequest(BaseModel):
    market: str = "us"
    symbol: str
    active: bool = True


class MarketWatchlistResponse(BaseModel):
    id: int
    market: str
    symbol: str
    active: bool


class MarketIngestRequest(BaseModel):
    source: str = "all"
    start_date: date | None = None
    end_date: date | None = None


class MarketIngestResponse(BaseModel):
    results: list[dict[str, Any]]


class MarketSanityResponse(BaseModel):
    market: str
    symbol: str
    first_date: str | None
    last_date: str | None
    row_count: int
    gap_count: int
    note: str | None = None


class MarketIngestRunResponse(BaseModel):
    id: int
    source: str
    run_date: str
    status: str
    detail: str | None
    started_at: str
    finished_at: str | None


class TradePlanCreateRequest(BaseModel):
    market: str
    symbol: str
    direction: str
    planned_entry: Decimal
    stop_price: Decimal
    target_price: Decimal | None = None
    quantity: Decimal
    declared_capital_twd: Decimal
    thesis: str
    strategy_spec_id: int | None = None
    is_paper: bool = True
    created_by: str | None = None

    class Config:
        extra = "forbid"


class TradePlanResponse(BaseModel):
    id: int
    decision_request_id: int
    market: str
    symbol: str
    direction: str
    planned_entry: str
    stop_price: str
    target_price: str | None
    quantity: str
    declared_capital_twd: str
    thesis: str
    strategy_spec_id: int | None
    is_paper: bool
    risk_check: dict[str, Any]
    created_at: str


class TradePlanCreateResponse(TradePlanResponse):
    decision_request_status: str
    decision_request_risk_level: str


class TradePlanCloseRequest(BaseModel):
    exit_price: Decimal
    exit_at: datetime | None = None
    notes: str | None = None

    class Config:
        extra = "forbid"


class PlanOutcomeResponse(BaseModel):
    id: int
    trade_plan_id: int
    exit_price: str
    exit_at: str
    gross_pnl: str
    stop_respected: bool
    notes: str | None
    holding_days: int | None
    planned_vs_actual: dict[str, Any] | None
    currency: str
    created_at: str


class PlanMarkResponse(BaseModel):
    id: int
    trade_plan_id: int
    mark_date: str
    close_price: str


class BacktestRunRequest(BaseModel):
    spec: dict[str, Any]

    class Config:
        extra = "forbid"


class StrategySpecResponse(BaseModel):
    id: int
    name: str
    market: str
    symbol: str
    direction: str
    spec_snapshot: dict[str, Any]
    created_at: str


class BacktestRunResponse(BaseModel):
    id: int
    strategy_spec_id: int
    range_start: str
    range_end: str
    spec_snapshot: dict[str, Any]
    cost_params: dict[str, Any]
    results: dict[str, Any]
    run_hash: str
    created_at: str


class BacktestRunCreateResponse(BacktestRunResponse):
    created: bool


class ToolMonitorSettingsRequest(BaseModel):
    enabled: bool | None = None
    flight_no: str | None = None
    flight_date: date | None = None
    interval_minutes: int | None = None


class ToolMonitorSettingsResponse(BaseModel):
    id: int
    kind: str
    enabled: bool
    flight_no: str
    flight_date: str
    interval_minutes: int
    last_run_at: str | None
    last_status_ok: bool | None
    last_status_display: str | None
    last_status_fail_count: int
    updated_at: str


class FlightStatusRequest(BaseModel):
    flight_no: str = "AK1511"
    flight_date: str = "2026-07-10"


class FlightStatusResponse(BaseModel):
    flight_no: str
    flight_date: str
    status: str | None
    display: str
    raw: dict[str, Any]


class MonitorTickResponse(BaseModel):
    skipped: bool
    reason: str | None
    ran_at: str | None
    status_ok: bool | None
    display: str | None
    notified: bool


class PointProgramRequest(BaseModel):
    name: str
    kind: str
    expiry_rule_note: str | None = None


class PointProgramResponse(BaseModel):
    id: int
    name: str
    kind: str
    expiry_rule_note: str | None


class PointAccountRequest(BaseModel):
    owner: str
    program_id: int
    account_ref: str | None = None
    status: str = "active"
    last_activity: date | None = None
    notes: str | None = None


class PointAccountResponse(BaseModel):
    id: int
    owner: str
    program_id: int
    account_ref: str | None
    status: str
    last_activity: str | None
    notes: str | None


class LedgerTransactionRequest(BaseModel):
    account_id: int
    kind: str
    quantity: Decimal
    occurred_at: date
    counterparty_account_id: int | None = None
    cost_total: Decimal | None = None
    cost_currency: str | None = None
    note: str | None = None
    create_lot: bool = False


class LedgerTransactionResponse(BaseModel):
    id: int
    account_id: int
    kind: str
    quantity: str
    occurred_at: str
    counterparty_account_id: int | None
    cost_total: str | None
    cost_currency: str | None
    note: str | None


class CostLotResponse(BaseModel):
    id: int
    account_id: int
    source_transaction_id: int
    quantity: str
    remaining_quantity: str
    total_cost_twd: str
    cost_per_point_twd: str
    acquired_at: str


class TransferRuleRequest(BaseModel):
    from_program_id: int
    to_program_id: int
    ratio_from: Decimal
    ratio_to: Decimal
    bonus_pct: Decimal = Decimal("0")
    min_transfer: Decimal | None = None
    transfer_days_note: str | None = None
    valid_from: date
    valid_until: date | None = None
    rule_kind: str = "linear"
    block_size: Decimal | None = None
    block_bonus_points: Decimal | None = None
    source_url: str | None = None


class TransferRuleResponse(BaseModel):
    id: int
    from_program_id: int
    to_program_id: int
    ratio_from: str
    ratio_to: str
    bonus_pct: str
    min_transfer: str | None
    transfer_days_note: str | None
    valid_from: str
    valid_until: str | None
    rule_kind: str
    block_size: str | None
    block_bonus_points: str | None
    source_url: str | None


class WalletAiParseRuleRequest(BaseModel):
    source_program_name: str
    pasted_text: str


class WalletAiParsedRule(BaseModel):
    from_program_name: str | None = None
    to_program_name: str | None = None
    ratio_from: str | None = None
    ratio_to: str | None = None
    bonus_pct: str | None = None
    min_transfer: str | None = None
    rule_kind: str | None = None
    block_size: str | None = None
    block_bonus_points: str | None = None
    valid_until: str | None = None
    source_url: str | None = None
    note: str | None = None


class WalletAiParseRuleResponse(BaseModel):
    status: str
    preview: WalletAiParsedRule | None
    message: str


class PurchaseOfferRequest(BaseModel):
    program_id: int
    kind: str
    base_price: Decimal
    currency: str
    bonus_pct: Decimal = Decimal("0")
    min_points: Decimal | None = None
    max_points: Decimal | None = None
    start_date: date
    end_date: date | None = None
    source_note: str | None = None
    paid_amount: Decimal | None = None
    fees: Decimal | None = None
    rebate: Decimal | None = None
    points_received: Decimal | None = None
    source_url: str | None = None


class PurchaseOfferResponse(BaseModel):
    id: int
    program_id: int
    kind: str
    base_price: str
    currency: str
    bonus_pct: str
    min_points: str | None
    max_points: str | None
    effective_cpp: str
    start_date: str
    end_date: str | None
    source_note: str | None
    paid_amount: str | None
    fees: str | None
    rebate: str | None
    points_received: str | None
    source_url: str | None


class AwardQuoteRequest(BaseModel):
    origin: str | None = None
    destination: str | None = None
    travel_date: date | None = None
    cabin: str | None = None
    pax: int = 1
    program_id: int
    miles_required: Decimal
    taxes_amount: Decimal | None = None
    taxes_currency: str | None = None
    cash_price_twd: Decimal | None = None
    source: str = "manual"
    note: str | None = None


class AwardQuoteResponse(BaseModel):
    id: int
    origin: str | None
    destination: str | None
    travel_date: str | None
    cabin: str | None
    pax: int
    program_id: int
    miles_required: str
    taxes_amount: str | None
    taxes_currency: str | None
    cash_price_twd: str | None
    source: str
    note: str | None
    created_at: str


class TripQuestRunRequest(BaseModel):
    origin: str
    destination: str
    programs: list[str]
    window_start: date
    window_end: date
    trip_days: int
    cabin: str
    pax: int = 1


class TripQuestResponse(BaseModel):
    id: int
    origin: str
    destination: str
    programs: list[str]
    window_start: str
    window_end: str
    trip_days: int
    cabin: str
    pax: int
    created_at: str


class QuestResultResponse(BaseModel):
    id: int
    trip_quest_id: int
    run_date: str
    rank: int
    program: str
    outbound_date: str
    return_date: str
    outbound_miles: str
    return_miles: str
    total_miles: str
    outbound_taxes: str | None
    return_taxes: str | None
    seats_min: int
    raw_refs: str | None


class TripQuestRunResponse(BaseModel):
    quest: TripQuestResponse
    results: list[QuestResultResponse]
    created_results: int


class AwardEvaluateRequest(BaseModel):
    evaluation_date: date | None = None


class FundingScenarioResponse(BaseModel):
    id: int
    award_quote_id: int
    evaluated_at: str
    owner: str
    method: str
    path_json: str
    true_cost_twd: str
    saving_vs_cash_twd: str | None
    rank: int
    warnings: str | None
    effective_cpp: str | None
    total_cash_cost_twd: str
    points_acquired: str
    points_consumed: str
    points_leftover: str


class AwardWatchRequest(BaseModel):
    origin: str
    destination: str
    cabin: str
    start_date: date | None = None
    end_date: date | None = None
    program_id: int | None = None
    active: bool = True
    note: str | None = None


class AwardWatchResponse(BaseModel):
    id: int
    origin: str
    destination: str
    cabin: str
    start_date: str | None
    end_date: str | None
    program_id: int | None
    active: bool
    note: str | None
    created_at: str
    updated_at: str


class AwardWatchFetchRequest(BaseModel):
    seen_date: date | None = None


class AwardSnapshotResponse(BaseModel):
    id: int
    watch_id: int
    seen_date: str
    status: str
    result_count: int
    normalized_json: str
    created_at: str


class AwardSnapshotPromoteRequest(BaseModel):
    item_index: int = 0


class AwardSnapshotPromoteResponse(BaseModel):
    award_quote: AwardQuoteResponse


class ExpiryAlertResponse(BaseModel):
    id: int
    account_id: int | None
    voucher_id: int | None
    threshold_days: int
    expires_at: str
    checked_on: str
    balance: str
    status: str
    message: str
    created_at: str


class HotelVoucherRequest(BaseModel):
    owner: str
    program_id: int
    face_value_points: Decimal
    expires_at: date
    acquired_note: str | None = None


class HotelVoucherStatusRequest(BaseModel):
    status: str
    used_note: str | None = None

    class Config:
        extra = "forbid"


class HotelVoucherResponse(BaseModel):
    id: int
    owner: str
    program_id: int
    program_name: str
    face_value_points: str
    expires_at: str
    status: str
    acquired_note: str | None
    used_note: str | None
    created_at: str


class HotelStayQuoteRequest(BaseModel):
    owner: str
    hotel_name: str
    stay_date: date
    nights: int = 1
    program_id: int
    cash_price_twd: Decimal
    points_price_per_night: Decimal
    taxes_note: str | None = None
    topup_allowed: bool = False
    topup_points: Decimal | None = None


class HotelStayQuoteResponse(BaseModel):
    id: int
    owner: str
    hotel_name: str
    stay_date: str
    nights: int
    program_id: int
    program_name: str
    cash_price_twd: str
    points_price_per_night: str
    taxes_note: str | None
    topup_allowed: bool
    topup_points: str | None
    created_at: str


class HotelStayEvaluationResponse(BaseModel):
    quote: dict[str, Any]
    cpp: str
    total_points: str
    options: list[dict[str, Any]]
    notes: list[str]


class FxRateResponse(BaseModel):
    id: int
    currency: str
    twd_per_unit: str
    as_of: str
    source: str


class FxRefreshResponse(BaseModel):
    source: str
    created: str


class PointWalletPortfolioResponse(BaseModel):
    owners: list[str]
    accounts: list[dict[str, Any]]
    expiring_soon: list[dict[str, Any]]
    total_real_cost_basis_twd: str


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


@app.get("/capital/market-data/watchlist", response_model=list[MarketWatchlistResponse])
def get_capital_market_watchlist(market: str | None = None, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_market_watchlist_response(row) for row in list_watchlist_symbols(session, market=market)]


@app.post("/capital/market-data/watchlist", response_model=MarketWatchlistResponse)
def post_capital_market_watchlist(payload: MarketWatchlistRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        row = create_watchlist_symbol(session, market=payload.market, symbol=payload.symbol, active=payload.active)
    except MarketDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _market_watchlist_response(row)


@app.patch("/capital/market-data/watchlist/{symbol_id}", response_model=MarketWatchlistResponse)
def patch_capital_market_watchlist(
    symbol_id: int,
    payload: MarketWatchlistRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = update_watchlist_symbol(session, symbol_id=symbol_id, active=payload.active)
    except MarketDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _market_watchlist_response(row)


@app.delete("/capital/market-data/watchlist/{symbol_id}")
def delete_capital_market_watchlist(symbol_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    try:
        delete_watchlist_symbol(session, symbol_id=symbol_id)
    except MarketDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@app.post("/capital/market-data/ingest", response_model=MarketIngestResponse)
def post_capital_market_data_ingest(payload: MarketIngestRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    source = payload.source.lower()
    if source not in {"taifex", "yahoo", "all"}:
        raise HTTPException(status_code=422, detail="source must be taifex, yahoo, or all")
    end_date = payload.end_date or date.today()
    start_date = payload.start_date or end_date - timedelta(days=365 * 3 + 7)
    results = []
    if source in {"taifex", "all"}:
        results.append(_market_ingest_result_response(ingest_taifex(session, start_date=start_date, end_date=end_date)))
    if source in {"yahoo", "all"}:
        results.append(_market_ingest_result_response(ingest_yahoo_us(session)))
    return {"results": results}


@app.get("/capital/market-data/sanity", response_model=list[MarketSanityResponse])
def get_capital_market_data_sanity(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return market_sanity_summary(session)


@app.get("/capital/market-data/ingest-runs", response_model=list[MarketIngestRunResponse])
def get_capital_market_data_ingest_runs(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_market_ingest_run_response(row) for row in list_ingest_runs(session)]


@app.get("/capital/trade-plans", response_model=list[TradePlanResponse])
def get_capital_trade_plans(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_trade_plan_response(row) for row in list_trade_plans(session)]


@app.post("/capital/trade-plans", response_model=TradePlanCreateResponse)
def post_capital_trade_plan(payload: TradePlanCreateRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        plan = create_trade_plan(
            session,
            market=payload.market,
            symbol=payload.symbol,
            direction=payload.direction,
            planned_entry=payload.planned_entry,
            stop_price=payload.stop_price,
            target_price=payload.target_price,
            quantity=payload.quantity,
            declared_capital_twd=payload.declared_capital_twd,
            thesis=payload.thesis,
            strategy_spec_id=payload.strategy_spec_id,
            is_paper=payload.is_paper,
            created_by=payload.created_by,
        )
    except TradePlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    request = get_decision_request(session, plan.decision_request_id)
    response = _trade_plan_response(plan)
    response.update(
        {
            "decision_request_status": request.status.value if request is not None else "unknown",
            "decision_request_risk_level": request.risk_level.value if request is not None else "unknown",
        }
    )
    return response


@app.post("/capital/trade-plans/mark")
def post_capital_trade_plan_mark(mark_date: date | None = None, session: Session = Depends(get_session)) -> dict[str, Any]:
    result = mark_open_trade_plans(session, mark_date=mark_date)
    return {"inserted": result.inserted, "skipped": result.skipped, "warnings": result.warnings}


@app.post("/capital/trade-plans/{plan_id}/close", response_model=PlanOutcomeResponse)
def post_capital_trade_plan_close(
    plan_id: int,
    payload: TradePlanCloseRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        outcome = close_trade_plan(
            session,
            plan_id=plan_id,
            exit_price=payload.exit_price,
            exit_at=payload.exit_at or datetime.now(timezone.utc),
            notes=payload.notes,
        )
    except TradePlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TradePlanOutcomeExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TradePlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _plan_outcome_response(outcome)


@app.get("/capital/trade-plans/stats")
def get_capital_trade_plan_stats(session: Session = Depends(get_session)) -> dict[str, Any]:
    return trade_plan_stats(session)


@app.get("/capital/backtests/specs", response_model=list[StrategySpecResponse])
def get_capital_backtest_specs(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_strategy_spec_response(row) for row in list_strategy_specs(session)]


@app.get("/capital/backtests/runs", response_model=list[BacktestRunResponse])
def get_capital_backtest_runs(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_backtest_run_response(row) for row in list_backtest_runs(session)]


@app.get("/capital/backtests/runs/{run_id}", response_model=BacktestRunResponse)
def get_capital_backtest_run(run_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = get_backtest_run(session, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="backtest run not found")
    return _backtest_run_response(row)


@app.post("/capital/backtests/run", response_model=BacktestRunCreateResponse)
def post_capital_backtest_run(payload: BacktestRunRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        result = run_backtest(session, payload.spec)
    except BacktestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = _backtest_run_response(result.backtest_run)
    response["created"] = result.created
    return response


@app.get("/tools/monitors/flight_watch", response_model=ToolMonitorSettingsResponse)
def get_tools_flight_watch_settings(session: Session = Depends(get_session)) -> dict[str, Any]:
    row = get_or_create_flight_watch_settings(session)
    return _tool_monitor_settings_response(row)


@app.patch("/tools/monitors/flight_watch", response_model=ToolMonitorSettingsResponse)
def patch_tools_flight_watch_settings(
    payload: ToolMonitorSettingsRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = update_flight_watch_settings(
            session,
            enabled=payload.enabled,
            flight_no=payload.flight_no,
            flight_date=payload.flight_date,
            interval_minutes=payload.interval_minutes,
        )
    except ToolMonitorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _tool_monitor_settings_response(row)


@app.post("/tools/flight-status", response_model=FlightStatusResponse)
def post_tools_flight_status(payload: FlightStatusRequest) -> dict[str, Any]:
    try:
        return query_flight_status(payload.flight_no, payload.flight_date)
    except Exception as exc:  # noqa: BLE001 - external fetch, fail loud with detail
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/tools/monitors/tick", response_model=MonitorTickResponse)
def post_tools_monitor_tick(session: Session = Depends(get_session)) -> dict[str, Any]:
    result = tick_flight_watch(session)
    return {
        "skipped": result.skipped,
        "reason": result.reason,
        "ran_at": result.ran_at.isoformat() if result.ran_at else None,
        "status_ok": result.status_ok,
        "display": result.display,
        "notified": result.notified,
    }


@app.get("/wallet/programs", response_model=list[PointProgramResponse])
def get_wallet_programs(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_point_program_response(row) for row in list_programs(session)]


@app.post("/wallet/programs", response_model=PointProgramResponse)
def post_wallet_program(
    request: PointProgramRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_program(
            session,
            name=request.name,
            kind=request.kind,
            expiry_rule_note=request.expiry_rule_note,
        )
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Program already exists") from exc
    return _point_program_response(row)


@app.get("/wallet/accounts", response_model=list[PointAccountResponse])
def get_wallet_accounts(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_point_account_response(row) for row in list_accounts(session)]


@app.post("/wallet/accounts", response_model=PointAccountResponse)
def post_wallet_account(
    request: PointAccountRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_account(
            session,
            owner=request.owner,
            program_id=request.program_id,
            account_ref=request.account_ref,
            status=request.status,
            last_activity=request.last_activity,
            notes=request.notes,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail="Account already exists for owner/program") from exc
    return _point_account_response(row)


@app.get("/wallet/ledger", response_model=list[LedgerTransactionResponse])
def get_wallet_ledger(
    account_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [_ledger_transaction_response(row) for row in list_ledger_transactions(session, account_id)]


@app.post("/wallet/ledger", response_model=LedgerTransactionResponse)
def post_wallet_ledger(
    request: LedgerTransactionRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_ledger_transaction(
            session,
            account_id=request.account_id,
            kind=request.kind,
            quantity=request.quantity,
            occurred_at=request.occurred_at,
            counterparty_account_id=request.counterparty_account_id,
            cost_total=request.cost_total,
            cost_currency=request.cost_currency,
            note=request.note,
            create_lot=request.create_lot,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _ledger_transaction_response(row)


@app.get("/wallet/cost-lots", response_model=list[CostLotResponse])
def get_wallet_cost_lots(
    account_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [_cost_lot_response(row) for row in list_cost_lots(session, account_id)]


@app.get("/wallet/transfer-rules", response_model=list[TransferRuleResponse])
def get_wallet_transfer_rules(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_transfer_rule_response(row) for row in list_transfer_rules(session)]


@app.post("/wallet/transfer-rules", response_model=TransferRuleResponse)
def post_wallet_transfer_rule(
    request: TransferRuleRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_transfer_rule(
            session,
            from_program_id=request.from_program_id,
            to_program_id=request.to_program_id,
            ratio_from=request.ratio_from,
            ratio_to=request.ratio_to,
            bonus_pct=request.bonus_pct,
            min_transfer=request.min_transfer,
            transfer_days_note=request.transfer_days_note,
            valid_from=request.valid_from,
            valid_until=request.valid_until,
            rule_kind=request.rule_kind,
            block_size=request.block_size,
            block_bonus_points=request.block_bonus_points,
            source_url=request.source_url,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _transfer_rule_response(row)


@app.patch("/wallet/transfer-rules/{rule_id}", response_model=TransferRuleResponse)
def patch_wallet_transfer_rule(
    rule_id: int,
    request: TransferRuleRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(TransferRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown transfer_rule_id: {rule_id}")
    try:
        _require_wallet_program(session, request.from_program_id)
        _require_wallet_program(session, request.to_program_id)
        row.from_program_id = request.from_program_id
        row.to_program_id = request.to_program_id
        row.ratio_from = request.ratio_from
        row.ratio_to = request.ratio_to
        row.bonus_pct = request.bonus_pct
        row.min_transfer = request.min_transfer
        row.transfer_days_note = request.transfer_days_note
        row.valid_from = request.valid_from
        row.valid_until = request.valid_until
        row.rule_kind = request.rule_kind
        row.block_size = request.block_size
        row.block_bonus_points = request.block_bonus_points
        row.source_url = request.source_url
        session.commit()
    except PointWalletNotFoundError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _transfer_rule_response(row)


@app.delete("/wallet/transfer-rules/{rule_id}")
def delete_wallet_transfer_rule(
    rule_id: int,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    row = session.get(TransferRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown transfer_rule_id: {rule_id}")
    session.delete(row)
    session.commit()
    return {"status": "deleted"}


@app.post("/wallet/ai-parse-rule", response_model=WalletAiParseRuleResponse)
def post_wallet_ai_parse_rule(request: WalletAiParseRuleRequest) -> dict[str, Any]:
    if not request.pasted_text.strip():
        raise HTTPException(status_code=422, detail="請貼上促銷文字或公告內容")
    parsed = _parse_wallet_rule_with_deepseek(request.source_program_name, request.pasted_text)
    if parsed is None:
        return {"status": "failed", "preview": None, "message": "解析失敗，請手動輸入"}
    parsed["note"] = "AI解析-待確認"
    return {"status": "preview", "preview": parsed, "message": "已解析成待確認規則，請人工確認後再加入"}


@app.get("/wallet/purchase-offers", response_model=list[PurchaseOfferResponse])
def get_wallet_purchase_offers(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_purchase_offer_response(row) for row in list_purchase_offers(session)]


@app.post("/wallet/purchase-offers", response_model=PurchaseOfferResponse)
def post_wallet_purchase_offer(
    request: PurchaseOfferRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_purchase_offer(
            session,
            program_id=request.program_id,
            kind=request.kind,
            base_price=request.base_price,
            currency=request.currency,
            bonus_pct=request.bonus_pct,
            min_points=request.min_points,
            max_points=request.max_points,
            start_date=request.start_date,
            end_date=request.end_date,
            source_note=request.source_note,
            paid_amount=request.paid_amount,
            fees=request.fees,
            rebate=request.rebate,
            points_received=request.points_received,
            source_url=request.source_url,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _purchase_offer_response(row)


@app.get("/wallet/fx-rates", response_model=list[FxRateResponse])
def get_wallet_fx_rates(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_fx_rate_response(row) for row in list_fx_rates(session)]


@app.post("/wallet/fx-rates/refresh", response_model=FxRefreshResponse)
def post_wallet_fx_refresh(session: Session = Depends(get_session)) -> dict[str, str]:
    return refresh_fx_rates(session)


@app.get("/wallet/portfolio", response_model=PointWalletPortfolioResponse)
def get_wallet_portfolio(
    owner: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return _point_wallet_portfolio_response(get_portfolio_summary(session, owner=owner))
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/wallet/hotel-vouchers", response_model=list[HotelVoucherResponse])
def get_wallet_hotel_vouchers(
    owner: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    try:
        return [_hotel_voucher_response(row) for row in list_hotel_vouchers(session, owner=owner, status=status)]
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/wallet/hotel-vouchers", response_model=HotelVoucherResponse)
def post_wallet_hotel_voucher(
    request: HotelVoucherRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_hotel_voucher(
            session,
            owner=request.owner,
            program_id=request.program_id,
            face_value_points=request.face_value_points,
            expires_at=request.expires_at,
            acquired_note=request.acquired_note,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _hotel_voucher_response(row)


@app.patch("/wallet/hotel-vouchers/{voucher_id}/status", response_model=HotelVoucherResponse)
def patch_wallet_hotel_voucher_status(
    voucher_id: int,
    request: HotelVoucherStatusRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = update_hotel_voucher_status(session, voucher_id=voucher_id, status=request.status, used_note=request.used_note)
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _hotel_voucher_response(row)


@app.get("/wallet/hotel-stay-quotes", response_model=list[HotelStayQuoteResponse])
def get_wallet_hotel_stay_quotes(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_hotel_stay_quote_response(row) for row in list_hotel_stay_quotes(session)]


@app.post("/wallet/hotel-stay-quotes", response_model=HotelStayQuoteResponse)
def post_wallet_hotel_stay_quote(
    request: HotelStayQuoteRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_hotel_stay_quote(
            session,
            owner=request.owner,
            hotel_name=request.hotel_name,
            stay_date=request.stay_date,
            nights=request.nights,
            program_id=request.program_id,
            cash_price_twd=request.cash_price_twd,
            points_price_per_night=request.points_price_per_night,
            taxes_note=request.taxes_note,
            topup_allowed=request.topup_allowed,
            topup_points=request.topup_points,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _hotel_stay_quote_response(row)


@app.post("/wallet/hotel-stay-quotes/{quote_id}/evaluate", response_model=HotelStayEvaluationResponse)
def post_wallet_hotel_stay_quote_evaluate(
    quote_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return evaluate_hotel_stay_quote(session, quote_id)
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/wallet/award-quotes", response_model=list[AwardQuoteResponse])
def get_wallet_award_quotes(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_award_quote_response(row) for row in list_award_quotes(session)]


@app.post("/wallet/award-quotes", response_model=AwardQuoteResponse)
def post_wallet_award_quote(
    request: AwardQuoteRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_award_quote(
            session,
            origin=request.origin,
            destination=request.destination,
            travel_date=request.travel_date,
            cabin=request.cabin,
            pax=request.pax,
            program_id=request.program_id,
            miles_required=request.miles_required,
            taxes_amount=request.taxes_amount,
            taxes_currency=request.taxes_currency,
            cash_price_twd=request.cash_price_twd,
            source=request.source,
            note=request.note,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _award_quote_response(row)


@app.get("/wallet/award-quotes/{quote_id}", response_model=AwardQuoteResponse)
def get_wallet_award_quote(
    quote_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        return _award_quote_response(get_award_quote(session, quote_id))
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/wallet/award-quotes/{quote_id}/evaluate", response_model=list[FundingScenarioResponse])
def post_wallet_award_quote_evaluate(
    quote_id: int,
    request: AwardEvaluateRequest,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    try:
        rows = evaluate_award_quote(session, quote_id, evaluation_date=request.evaluation_date)
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [_funding_scenario_response(row) for row in rows]


@app.get("/wallet/award-quotes/{quote_id}/scenarios", response_model=list[FundingScenarioResponse])
def get_wallet_award_quote_scenarios(
    quote_id: int,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    try:
        get_award_quote(session, quote_id)
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_funding_scenario_response(row) for row in list_funding_scenarios(session, quote_id)]


@app.get("/wallet/award-watches", response_model=list[AwardWatchResponse])
def get_wallet_award_watches(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_award_watch_response(row) for row in list_award_watches(session)]


@app.post("/wallet/award-watches", response_model=AwardWatchResponse)
def post_wallet_award_watch(
    request: AwardWatchRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = create_award_watch(
            session,
            origin=request.origin,
            destination=request.destination,
            cabin=request.cabin,
            start_date=request.start_date,
            end_date=request.end_date,
            program_id=request.program_id,
            active=request.active,
            note=request.note,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _award_watch_response(row)


@app.patch("/wallet/award-watches/{watch_id}", response_model=AwardWatchResponse)
def patch_wallet_award_watch(
    watch_id: int,
    request: AwardWatchRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        row = update_award_watch(
            session,
            watch_id=watch_id,
            origin=request.origin,
            destination=request.destination,
            cabin=request.cabin,
            start_date=request.start_date,
            end_date=request.end_date,
            program_id=request.program_id,
            active=request.active,
            note=request.note,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _award_watch_response(row)


@app.delete("/wallet/award-watches/{watch_id}")
def delete_wallet_award_watch(watch_id: int, session: Session = Depends(get_session)) -> dict[str, str]:
    try:
        delete_award_watch(session, watch_id=watch_id)
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}


@app.post("/wallet/award-watches/{watch_id}/fetch", response_model=AwardSnapshotResponse)
def post_wallet_award_watch_fetch(
    watch_id: int,
    request: AwardWatchFetchRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        result = fetch_award_watch(session, watch_id=watch_id, seen_date=request.seen_date)
    except SeatsAeroError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _award_snapshot_response(result.snapshot)


@app.get("/wallet/award-snapshots", response_model=list[AwardSnapshotResponse])
def get_wallet_award_snapshots(
    watch_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [_award_snapshot_response(row) for row in list_award_snapshots(session, watch_id=watch_id)]


@app.post("/wallet/award-snapshots/{snapshot_id}/promote", response_model=AwardSnapshotPromoteResponse)
def post_wallet_award_snapshot_promote(
    snapshot_id: int,
    request: AwardSnapshotPromoteRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        quote = promote_snapshot_to_award_quote(session, snapshot_id=snapshot_id, item_index=request.item_index)
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PointWalletError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"award_quote": _award_quote_response(quote)}


@app.get("/wallet/trip-quests", response_model=list[TripQuestResponse])
def get_wallet_trip_quests(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_trip_quest_response(row) for row in list_trip_quests(session)]


@app.post("/wallet/trip-quests/run", response_model=TripQuestRunResponse)
def post_wallet_trip_quest_run(
    request: TripQuestRunRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        run = run_trip_quest(
            session,
            origin=request.origin,
            destination=request.destination,
            programs=request.programs,
            window_start=request.window_start,
            window_end=request.window_end,
            trip_days=request.trip_days,
            cabin=request.cabin,
            pax=request.pax,
        )
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SeatsAeroError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TripQuestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "quest": _trip_quest_response(run.quest),
        "results": [_quest_result_response(row) for row in run.results],
        "created_results": run.created_results,
    }


@app.get("/wallet/trip-quests/{quest_id}/results", response_model=list[QuestResultResponse])
def get_wallet_trip_quest_results(
    quest_id: int,
    run_date: date | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    try:
        get_trip_quest(session, quest_id)
    except PointWalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_quest_result_response(row) for row in list_quest_results(session, quest_id=quest_id, run_date=run_date)]


@app.get("/wallet/expiry-alerts", response_model=list[ExpiryAlertResponse])
def get_wallet_expiry_alerts(
    status: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [_expiry_alert_response(row) for row in list_expiry_alerts(session, status=status)]


@app.post("/wallet/expiry-alerts/scan", response_model=list[ExpiryAlertResponse])
def post_wallet_expiry_alert_scan(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [_expiry_alert_response(row) for row in scan_expiry_alerts(session)]


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


def _parse_wallet_rule_with_deepseek(source_program_name: str, pasted_text: str) -> dict[str, str | None] | None:
    prompt = (
        "你是點數轉點規則解析器。只根據使用者貼上的文字輸出嚴格 JSON，"
        "不得猜測文字中沒有的比例或期限。JSON 欄位只能包含："
        "from_program_name,to_program_name,ratio_from,ratio_to,bonus_pct,min_transfer,"
        "rule_kind,block_size,block_bonus_points,valid_until,source_url,note。"
        "rule_kind 只能是 linear 或 threshold_block。沒有資料填 null。"
        f"\n來源計畫：{source_program_name}\n貼上文字：\n{pasted_text}"
    )
    response = DeepSeekProvider().chat(LLMRequest(role=ModelRole.SUMMARIZER, prompt=prompt))
    if response.dry_run:
        return None
    try:
        payload = json.loads(response.content)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    allowed = {
        "from_program_name",
        "to_program_name",
        "ratio_from",
        "ratio_to",
        "bonus_pct",
        "min_transfer",
        "rule_kind",
        "block_size",
        "block_bonus_points",
        "valid_until",
        "source_url",
        "note",
    }
    parsed = {key: _optional_string(payload.get(key)) for key in allowed}
    if not parsed.get("ratio_from") or not parsed.get("ratio_to") or not parsed.get("to_program_name"):
        return None
    parsed["from_program_name"] = parsed.get("from_program_name") or source_program_name
    parsed["bonus_pct"] = parsed.get("bonus_pct") or "0"
    parsed["rule_kind"] = parsed.get("rule_kind") or "linear"
    return parsed


def _require_wallet_program(session: Session, program_id: int) -> PointProgram:
    row = session.get(PointProgram, program_id)
    if row is None:
        raise PointWalletNotFoundError(f"Unknown program_id: {program_id}")
    return row


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _point_program_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "expiry_rule_note": row.expiry_rule_note,
    }


def _point_account_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "owner": row.owner,
        "program_id": row.program_id,
        "account_ref": row.account_ref,
        "status": row.status,
        "last_activity": row.last_activity.isoformat() if row.last_activity is not None else None,
        "notes": row.notes,
    }


def _ledger_transaction_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "kind": row.kind,
        "quantity": str(row.quantity),
        "occurred_at": row.occurred_at.isoformat(),
        "counterparty_account_id": row.counterparty_account_id,
        "cost_total": str(row.cost_total) if row.cost_total is not None else None,
        "cost_currency": row.cost_currency,
        "note": row.note,
    }


def _cost_lot_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "source_transaction_id": row.source_transaction_id,
        "quantity": str(row.quantity),
        "remaining_quantity": str(row.remaining_quantity),
        "total_cost_twd": str(row.total_cost_twd),
        "cost_per_point_twd": str(row.cost_per_point_twd),
        "acquired_at": row.acquired_at.isoformat(),
    }


def _transfer_rule_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "from_program_id": row.from_program_id,
        "to_program_id": row.to_program_id,
        "ratio_from": str(row.ratio_from),
        "ratio_to": str(row.ratio_to),
        "bonus_pct": str(row.bonus_pct),
        "min_transfer": str(row.min_transfer) if row.min_transfer is not None else None,
        "transfer_days_note": row.transfer_days_note,
        "valid_from": row.valid_from.isoformat(),
        "valid_until": row.valid_until.isoformat() if row.valid_until is not None else None,
        "rule_kind": row.rule_kind,
        "block_size": str(row.block_size) if row.block_size is not None else None,
        "block_bonus_points": str(row.block_bonus_points) if row.block_bonus_points is not None else None,
        "source_url": row.source_url,
    }


def _purchase_offer_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "program_id": row.program_id,
        "kind": row.kind,
        "base_price": str(row.base_price),
        "currency": row.currency,
        "bonus_pct": str(row.bonus_pct),
        "min_points": str(row.min_points) if row.min_points is not None else None,
        "max_points": str(row.max_points) if row.max_points is not None else None,
        "effective_cpp": str(row.effective_cpp),
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat() if row.end_date is not None else None,
        "source_note": row.source_note,
        "paid_amount": str(row.paid_amount) if row.paid_amount is not None else None,
        "fees": str(row.fees) if row.fees is not None else None,
        "rebate": str(row.rebate) if row.rebate is not None else None,
        "points_received": str(row.points_received) if row.points_received is not None else None,
        "source_url": row.source_url,
    }


def _fx_rate_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "currency": row.currency,
        "twd_per_unit": str(row.twd_per_unit),
        "as_of": row.as_of.isoformat(),
        "source": row.source,
    }


def _point_wallet_portfolio_response(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "owners": summary["owners"],
        "accounts": [_account_summary_response(row) for row in summary["accounts"]],
        "expiring_soon": [_account_summary_response(row) for row in summary["expiring_soon"]],
        "total_real_cost_basis_twd": str(summary["total_real_cost_basis_twd"]),
    }


def _award_quote_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "origin": row.origin,
        "destination": row.destination,
        "travel_date": row.travel_date.isoformat() if row.travel_date is not None else None,
        "cabin": row.cabin,
        "pax": row.pax,
        "program_id": row.program_id,
        "miles_required": str(row.miles_required),
        "taxes_amount": str(row.taxes_amount) if row.taxes_amount is not None else None,
        "taxes_currency": row.taxes_currency,
        "cash_price_twd": str(row.cash_price_twd) if row.cash_price_twd is not None else None,
        "source": row.source,
        "note": row.note,
        "created_at": row.created_at.isoformat(),
    }


def _trip_quest_response(row: TripQuest) -> dict[str, Any]:
    return {
        "id": row.id,
        "origin": row.origin,
        "destination": row.destination,
        "programs": json.loads(row.programs),
        "window_start": row.window_start.isoformat(),
        "window_end": row.window_end.isoformat(),
        "trip_days": row.trip_days,
        "cabin": row.cabin,
        "pax": row.pax,
        "created_at": row.created_at.isoformat(),
    }


def _quest_result_response(row: QuestResult) -> dict[str, Any]:
    return {
        "id": row.id,
        "trip_quest_id": row.trip_quest_id,
        "run_date": row.run_date.isoformat(),
        "rank": row.rank,
        "program": row.program,
        "outbound_date": row.outbound_date.isoformat(),
        "return_date": row.return_date.isoformat(),
        "outbound_miles": str(row.outbound_miles),
        "return_miles": str(row.return_miles),
        "total_miles": str(row.total_miles),
        "outbound_taxes": row.outbound_taxes,
        "return_taxes": row.return_taxes,
        "seats_min": row.seats_min,
        "raw_refs": row.raw_refs,
    }


def _funding_scenario_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "award_quote_id": row.award_quote_id,
        "evaluated_at": row.evaluated_at.isoformat(),
        "owner": row.owner,
        "method": row.method,
        "path_json": row.path_json,
        "true_cost_twd": str(row.true_cost_twd),
        "saving_vs_cash_twd": str(row.saving_vs_cash_twd) if row.saving_vs_cash_twd is not None else None,
        "rank": row.rank,
        "warnings": row.warnings,
        "effective_cpp": str(row.effective_cpp) if row.effective_cpp is not None else None,
        "total_cash_cost_twd": str(row.total_cash_cost_twd),
        "points_acquired": str(row.points_acquired),
        "points_consumed": str(row.points_consumed),
        "points_leftover": str(row.points_leftover),
    }


def _hotel_voucher_response(row: HotelVoucher) -> dict[str, Any]:
    return {
        "id": row.id,
        "owner": row.owner,
        "program_id": row.program_id,
        "program_name": row.program.name,
        "face_value_points": str(row.face_value_points),
        "expires_at": row.expires_at.isoformat(),
        "status": row.status,
        "acquired_note": row.acquired_note,
        "used_note": row.used_note,
        "created_at": row.created_at.isoformat(),
    }


def _hotel_stay_quote_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "owner": row.owner,
        "hotel_name": row.hotel_name,
        "stay_date": row.stay_date.isoformat(),
        "nights": row.nights,
        "program_id": row.program_id,
        "program_name": row.program.name,
        "cash_price_twd": str(row.cash_price_twd),
        "points_price_per_night": str(row.points_price_per_night),
        "taxes_note": row.taxes_note,
        "topup_allowed": row.topup_allowed,
        "topup_points": str(row.topup_points) if row.topup_points is not None else None,
        "created_at": row.created_at.isoformat(),
    }


def _award_watch_response(row: AwardWatch) -> dict[str, Any]:
    return {
        "id": row.id,
        "origin": row.origin,
        "destination": row.destination,
        "cabin": row.cabin,
        "start_date": row.start_date.isoformat() if row.start_date is not None else None,
        "end_date": row.end_date.isoformat() if row.end_date is not None else None,
        "program_id": row.program_id,
        "active": row.active,
        "note": row.note,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _award_snapshot_response(row: AwardSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "watch_id": row.watch_id,
        "seen_date": row.seen_date.isoformat(),
        "status": row.status,
        "result_count": row.result_count,
        "normalized_json": row.normalized_json,
        "created_at": row.created_at.isoformat(),
    }


def _expiry_alert_response(row: ExpiryAlert) -> dict[str, Any]:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "voucher_id": row.voucher_id,
        "threshold_days": row.threshold_days,
        "expires_at": row.expires_at.isoformat(),
        "checked_on": row.checked_on.isoformat(),
        "balance": str(row.balance),
        "status": row.status,
        "message": row.message,
        "created_at": row.created_at.isoformat(),
    }


def _market_watchlist_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "market": row.market,
        "symbol": row.symbol,
        "active": row.active,
    }


def _market_ingest_result_response(result) -> dict[str, Any]:
    return {
        "source": result.source,
        "status": result.status,
        "inserted": result.inserted,
        "skipped": result.skipped,
        "warnings": result.warnings,
    }


def _market_ingest_run_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "source": row.source,
        "run_date": row.run_date.isoformat(),
        "status": row.status,
        "detail": row.detail,
        "started_at": row.started_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at is not None else None,
    }


def _trade_plan_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "decision_request_id": row.decision_request_id,
        "market": row.market,
        "symbol": row.symbol,
        "direction": row.direction,
        "planned_entry": str(row.planned_entry),
        "stop_price": str(row.stop_price),
        "target_price": str(row.target_price) if row.target_price is not None else None,
        "quantity": str(row.quantity),
        "declared_capital_twd": str(row.declared_capital_twd),
        "thesis": row.thesis,
        "strategy_spec_id": row.strategy_spec_id,
        "is_paper": row.is_paper,
        "risk_check": json.loads(row.risk_check),
        "created_at": row.created_at.isoformat(),
    }


def _plan_outcome_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "trade_plan_id": row.trade_plan_id,
        "exit_price": str(row.exit_price),
        "exit_at": row.exit_at.isoformat(),
        "gross_pnl": str(row.gross_pnl),
        "stop_respected": row.stop_respected,
        "notes": row.notes,
        "holding_days": row.holding_days,
        "planned_vs_actual": json.loads(row.planned_vs_actual) if row.planned_vs_actual is not None else None,
        "currency": row.currency,
        "created_at": row.created_at.isoformat(),
    }


def _strategy_spec_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "market": row.market,
        "symbol": row.symbol,
        "direction": row.direction,
        "spec_snapshot": json.loads(row.spec_json),
        "created_at": row.created_at.isoformat(),
    }


def _backtest_run_response(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "strategy_spec_id": row.strategy_spec_id,
        "range_start": row.range_start.isoformat(),
        "range_end": row.range_end.isoformat(),
        "spec_snapshot": json.loads(row.spec_snapshot_json),
        "cost_params": json.loads(row.cost_params_json),
        "results": json.loads(row.results_json),
        "run_hash": row.run_hash,
        "created_at": row.created_at.isoformat(),
    }


def _tool_monitor_settings_response(row) -> dict[str, Any]:
    parsed = parse_tool_monitor_status(row.last_status)
    return {
        "id": row.id,
        "kind": row.kind,
        "enabled": row.enabled,
        "flight_no": row.flight_no,
        "flight_date": row.flight_date.isoformat(),
        "interval_minutes": row.interval_minutes,
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at is not None else None,
        "last_status_ok": parsed.get("ok") if parsed else None,
        "last_status_display": (parsed.get("display") or parsed.get("error")) if parsed else None,
        "last_status_fail_count": parsed.get("fail_count", 0) if parsed else 0,
        "updated_at": row.updated_at.isoformat(),
    }


def _account_summary_response(row) -> dict[str, Any]:
    return {
        "account_id": row.account_id,
        "owner": row.owner,
        "program_id": row.program_id,
        "program_name": row.program_name,
        "program_kind": row.program_kind,
        "balance": str(row.balance),
        "remaining_lot_quantity": str(row.remaining_lot_quantity),
        "real_cost_basis_twd": str(row.real_cost_basis_twd),
        "avg_cost_per_point_twd": str(row.avg_cost_per_point_twd) if row.avg_cost_per_point_twd is not None else None,
        "market_value_twd": str(row.market_value_twd) if row.market_value_twd is not None else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at is not None else None,
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
