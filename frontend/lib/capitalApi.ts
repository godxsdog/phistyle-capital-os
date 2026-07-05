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
