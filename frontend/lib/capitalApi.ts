const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type DecisionRequestStatus =
  | "submitted"
  | "triaged"
  | "brain_reviewed"
  | "human_approved"
  | "rejected"
  | "archived"
  | string;

export type CapitalDecisionListItem = {
  id: number;
  app_id: string;
  decision_type: string;
  question: string;
  context: string;
  options: string | null;
  risk_level: "low" | "medium" | "high" | string;
  status: DecisionRequestStatus;
  created_by: string | null;
  related_knowledge_document_id: number | null;
  related_decision_log_id: number | null;
  created_at: string;
  updated_at: string;
};

export type CapitalDecisionCreateRequest = {
  question: string;
  context: string;
  options: string;
  risk_level: "low" | "medium" | "high";
  created_by: string;
};

export type CapitalDecisionCreateResponse = {
  decision_request_id: number;
  app_id: "capital" | string;
  decision_type: "investment" | string;
  status: "submitted" | string;
};

export type CapitalPipelineRunResponse = {
  decision_request_id: number;
  decision_request_status: string;
  triage_result_id: number;
  triage_recommendation: string;
  brain_review_id: number;
  brain_recommendation: string;
  decision_log_id: number;
  decision_log_status: string;
  decision_log_approved_by: string | null;
  requires_human_review: boolean;
};

export type HumanReviewRequest = {
  reviewer: string;
  review_decision: "approve" | "reject";
  comment?: string | null;
};

export type HumanReviewResponse = {
  human_review_id: number;
  decision_log_id: number;
  decision_log_status: string;
  decision_request_id: number;
  decision_request_status: string;
  review_decision: "approve" | "reject" | string;
};

export type CapitalDecisionSummary = {
  decision_request: {
    id: number;
    question: string;
    context: string;
    options: string | null;
    risk_level: string;
    status: string;
  };
  triage_result: null | {
    id: number;
    recommendation: string;
  };
  brain_review: null | {
    id: number;
    recommendation: string;
    confidence: string;
    llm_backed: boolean | null;
    llm_provider: string | null;
    llm_model: string | null;
    llm_fallback_reason: string | null;
    llm_floor_applied: boolean | null;
  };
  decision_log: null | {
    id: number;
    status: string;
    approved_by: string | null;
  };
  human_review: null | {
    id: number;
    reviewer: string;
    review_decision: string;
  };
  requires_human_review: boolean;
};

export type TradeImportResponse = {
  batch_id: number;
  source: string;
  created: boolean;
  fill_count: number;
  cash_row_count: number;
  warning_count: number;
  warnings: string[];
};

export type ImportBatch = {
  id: number;
  source: string;
  content_hash: string;
  imported_at: string;
  fill_count: number;
  cash_row_count: number;
  warning_count: number;
  warnings: string[];
};

export type RealizedTrade = {
  id: number;
  import_batch_id: number;
  symbol: string;
  direction: string;
  opened_at: string | null;
  closed_at: string | null;
  quantity: string;
  avg_entry: string;
  avg_exit: string;
  gross_pnl: string;
  currency: string;
  holding_period_seconds: number | null;
};

export type TradeAttributionMetrics = {
  trade_count: number;
  gross_pnl: string;
  win_rate: number;
  expectancy: string;
  max_consecutive_losses: number;
  by_symbol: Array<Record<string, unknown>>;
  by_direction: Array<Record<string, unknown>>;
  by_instrument_type: Array<Record<string, unknown>>;
  by_holding_period: Array<Record<string, unknown>>;
  by_entry_weekday: Array<Record<string, unknown>>;
  by_entry_hour: Array<Record<string, unknown>>;
  averaging_down: Array<Record<string, unknown>>;
  leveraged_symbols: string[];
  narrative: {
    text: string;
    llm_backed: boolean;
    llm_provider: string | null;
    llm_model: string | null;
    fallback_reason: string | null;
  };
};

export type MarketWatchlistSymbol = {
  id: number;
  market: "us" | "taifex" | string;
  symbol: string;
  active: boolean;
};

export type MarketSanityRow = {
  market: string;
  symbol: string;
  first_date: string | null;
  last_date: string | null;
  row_count: number;
  gap_count: number;
  note: string | null;
};

export type MarketIngestRun = {
  id: number;
  source: string;
  run_date: string;
  status: string;
  detail: string | null;
  started_at: string;
  finished_at: string | null;
};

export type MarketIngestResult = {
  results: Array<{
    source: string;
    status: string;
    inserted: number;
    skipped: number;
    warnings: string[];
  }>;
};

export type TradePlan = {
  id: number;
  decision_request_id: number;
  market: string;
  symbol: string;
  direction: string;
  planned_entry: string;
  stop_price: string;
  target_price: string | null;
  quantity: string;
  declared_capital_twd: string;
  thesis: string;
  strategy_spec_id: number | null;
  is_paper: boolean;
  risk_check: {
    passed: boolean;
    forced_risk_level: string;
    checks: Array<{ rule: string; passed: boolean; message: string }>;
    risk_amount: string;
    risk_currency: string;
    risk_amount_twd: string;
    max_allowed_twd: string;
  };
  created_at: string;
};

export type TradePlanCreateResponse = TradePlan & {
  decision_request_status: string;
  decision_request_risk_level: string;
};

export type TradePlanCreateRequest = {
  market: "taifex" | "us";
  symbol: string;
  direction: "long" | "short";
  planned_entry: string;
  stop_price: string;
  target_price?: string | null;
  quantity: string;
  declared_capital_twd: string;
  thesis: string;
  strategy_spec_id?: number | null;
  is_paper: boolean;
  created_by: string;
};

export type PlanOutcome = {
  id: number;
  trade_plan_id: number;
  exit_price: string;
  exit_at: string;
  gross_pnl: string;
  stop_respected: boolean;
  notes: string | null;
  holding_days: number | null;
  planned_vs_actual: Record<string, unknown> | null;
  currency: string;
  created_at: string;
};

export type TradePlanStats = {
  total_closed_plan_count: number;
  by_currency: Array<{
    currency: string;
    closed_plan_count: number;
    win_rate: number;
    expectancy: string;
    gross_pnl: string;
    plan_adherence_rate: number;
  }>;
};

export type StrategySpec = {
  id: number;
  name: string;
  market: string;
  symbol: string;
  direction: string;
  spec_snapshot: Record<string, unknown>;
  created_at: string;
};

export type BacktestTrade = {
  entry_date: string;
  exit_date: string;
  entry_price: string;
  exit_price: string;
  gross_pnl: string;
  fee: string;
  tax: string;
  slippage: string;
  net_pnl: string;
  currency: string;
};

export type BacktestWindowResult = {
  trades: BacktestTrade[];
  equity_curve: Array<{ date: string; equity: string }>;
  metrics: {
    trade_count: number;
    net_pnl: string;
    max_drawdown: string;
    win_rate: number;
    expectancy: string;
    exposure_days: number;
  };
};

export type BacktestRun = {
  id: number;
  strategy_spec_id: number;
  range_start: string;
  range_end: string;
  spec_snapshot: Record<string, unknown>;
  cost_params: Record<string, unknown>;
  results: {
    cost_disclaimer?: string;
    tax_source_url?: string | null;
    known_limitations?: string[];
    split?: Record<string, unknown>;
    full?: BacktestWindowResult;
    in_sample?: BacktestWindowResult;
    out_of_sample?: BacktestWindowResult;
  };
  run_hash: string;
  created_at: string;
};

export type BacktestRunCreateResponse = BacktestRun & {
  created: boolean;
};

export async function listCapitalDecisions(): Promise<CapitalDecisionListItem[]> {
  return requestJson<CapitalDecisionListItem[]>("/capital/decisions");
}

export async function createCapitalDecision(
  payload: CapitalDecisionCreateRequest,
): Promise<CapitalDecisionCreateResponse> {
  return requestJson<CapitalDecisionCreateResponse>("/capital/decisions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCapitalDecision(decisionRequestId: number): Promise<CapitalDecisionSummary> {
  return requestJson<CapitalDecisionSummary>(`/capital/decisions/${decisionRequestId}`);
}

export async function runCapitalDecision(decisionRequestId: number): Promise<CapitalPipelineRunResponse> {
  return requestJson<CapitalPipelineRunResponse>(`/capital/decisions/${decisionRequestId}/run`, {
    method: "POST",
  });
}

export async function submitHumanReview(
  decisionLogId: number,
  payload: HumanReviewRequest,
): Promise<HumanReviewResponse> {
  return requestJson<HumanReviewResponse>(`/decisions/decision-logs/${decisionLogId}/human-review`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadTradeHistory(file: File): Promise<TradeImportResponse> {
  const formData = new FormData();
  formData.append("source", "schwab");
  formData.append("file", file);
  return requestFormJson<TradeImportResponse>("/capital/trade-imports", formData);
}

export async function listTradeImports(): Promise<ImportBatch[]> {
  return requestJson<ImportBatch[]>("/capital/trade-imports");
}

export async function listRealizedTrades(): Promise<RealizedTrade[]> {
  return requestJson<RealizedTrade[]>("/capital/realized-trades");
}

export async function getTradeAttribution(): Promise<TradeAttributionMetrics> {
  return requestJson<TradeAttributionMetrics>("/capital/trade-attribution");
}

export async function listMarketWatchlist(): Promise<MarketWatchlistSymbol[]> {
  return requestJson<MarketWatchlistSymbol[]>("/capital/market-data/watchlist");
}

export async function createMarketWatchlistSymbol(symbol: string): Promise<MarketWatchlistSymbol> {
  return requestJson<MarketWatchlistSymbol>("/capital/market-data/watchlist", {
    method: "POST",
    body: JSON.stringify({ market: "us", symbol, active: true }),
  });
}

export async function updateMarketWatchlistSymbol(id: number, symbol: string, active: boolean): Promise<MarketWatchlistSymbol> {
  return requestJson<MarketWatchlistSymbol>(`/capital/market-data/watchlist/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ market: "us", symbol, active }),
  });
}

export async function deleteMarketWatchlistSymbol(id: number): Promise<{ deleted: boolean }> {
  return requestJson<{ deleted: boolean }>(`/capital/market-data/watchlist/${id}`, {
    method: "DELETE",
  });
}

export async function runMarketIngest(source: "taifex" | "yahoo" | "all"): Promise<MarketIngestResult> {
  return requestJson<MarketIngestResult>("/capital/market-data/ingest", {
    method: "POST",
    body: JSON.stringify({ source }),
  });
}

export async function listMarketSanity(): Promise<MarketSanityRow[]> {
  return requestJson<MarketSanityRow[]>("/capital/market-data/sanity");
}

export async function listMarketIngestRuns(): Promise<MarketIngestRun[]> {
  return requestJson<MarketIngestRun[]>("/capital/market-data/ingest-runs");
}

export async function listTradePlans(): Promise<TradePlan[]> {
  return requestJson<TradePlan[]>("/capital/trade-plans");
}

export async function createTradePlan(payload: TradePlanCreateRequest): Promise<TradePlanCreateResponse> {
  return requestJson<TradePlanCreateResponse>("/capital/trade-plans", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function markTradePlans(): Promise<{ inserted: number; skipped: number; warnings: string[] }> {
  return requestJson<{ inserted: number; skipped: number; warnings: string[] }>("/capital/trade-plans/mark", {
    method: "POST",
  });
}

export async function closeTradePlan(planId: number, exitPrice: string, notes: string): Promise<PlanOutcome> {
  return requestJson<PlanOutcome>(`/capital/trade-plans/${planId}/close`, {
    method: "POST",
    body: JSON.stringify({ exit_price: exitPrice, notes }),
  });
}

export async function getTradePlanStats(): Promise<TradePlanStats> {
  return requestJson<TradePlanStats>("/capital/trade-plans/stats");
}

export async function listBacktestSpecs(): Promise<StrategySpec[]> {
  return requestJson<StrategySpec[]>("/capital/backtests/specs");
}

export async function listBacktestRuns(): Promise<BacktestRun[]> {
  return requestJson<BacktestRun[]>("/capital/backtests/runs");
}

export async function getBacktestRun(runId: number): Promise<BacktestRun> {
  return requestJson<BacktestRun>(`/capital/backtests/runs/${runId}`);
}

export async function runBacktest(spec: Record<string, unknown>): Promise<BacktestRunCreateResponse> {
  return requestJson<BacktestRunCreateResponse>("/capital/backtests/run", {
    method: "POST",
    body: JSON.stringify({ spec }),
  });
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      message = userFacingErrorMessage(payload.detail, message);
    } catch {
      // Keep the generic HTTP message.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

async function requestFormJson<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    body,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      message = userFacingErrorMessage(payload.detail, message);
    } catch {
      // Keep the generic HTTP message.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

function userFacingErrorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map(formatValidationIssue)
      .filter((message): message is string => Boolean(message));
    if (messages.length > 0) {
      return messages.join("; ");
    }
  }
  return fallback;
}

function formatValidationIssue(issue: unknown): string | null {
  if (!isValidationIssue(issue)) {
    return null;
  }
  const location = issue.loc
    .filter((part) => typeof part === "string" || typeof part === "number")
    .map(String)
    .filter((part) => part !== "body")
    .join(".");
  return location ? `${location}: ${issue.msg}` : issue.msg;
}

function isValidationIssue(value: unknown): value is { loc: unknown[]; msg: string } {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as { loc?: unknown; msg?: unknown };
  return Array.isArray(candidate.loc) && typeof candidate.msg === "string";
}
