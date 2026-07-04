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
