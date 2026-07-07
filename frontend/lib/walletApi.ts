const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Program = {
  id: number;
  name: string;
  kind: string;
  expiry_rule_note: string | null;
};

export type Account = {
  id: number;
  owner: "kent" | "wife" | string;
  program_id: number;
  account_ref: string | null;
  status: string;
  last_activity: string | null;
  notes: string | null;
};

export type LedgerTransaction = {
  id: number;
  account_id: number;
  kind: string;
  quantity: string;
  occurred_at: string;
  counterparty_account_id: number | null;
  cost_total: string | null;
  cost_currency: string | null;
  note: string | null;
};

export type TransferRule = {
  id: number;
  from_program_id: number;
  to_program_id: number;
  ratio_from: string;
  ratio_to: string;
  bonus_pct: string;
  min_transfer: string | null;
  transfer_days_note: string | null;
  valid_from: string;
  valid_until: string | null;
  rule_kind: string;
  block_size: string | null;
  block_bonus_points: string | null;
};

export type PurchaseOffer = {
  id: number;
  program_id: number;
  kind: string;
  base_price: string;
  currency: string;
  bonus_pct: string;
  effective_cpp: string;
  start_date: string;
  end_date: string | null;
  source_note: string | null;
  paid_amount: string | null;
  fees: string | null;
  rebate: string | null;
  points_received: string | null;
};

export type Portfolio = {
  owners: string[];
  total_real_cost_basis_twd: string;
  accounts: Array<Record<string, string | number | null>>;
  expiring_soon: Array<Record<string, string | number | null>>;
};

export type AwardQuote = {
  id: number;
  origin: string | null;
  destination: string | null;
  travel_date: string | null;
  cabin: string | null;
  pax: number;
  program_id: number;
  miles_required: string;
  taxes_amount: string | null;
  taxes_currency: string | null;
  cash_price_twd: string | null;
  source: string;
  created_at: string;
};

export type FundingScenario = {
  id: number;
  award_quote_id: number;
  evaluated_at: string;
  owner: string;
  method: string;
  path_json: string;
  true_cost_twd: string;
  saving_vs_cash_twd: string | null;
  rank: number;
  warnings: string | null;
  effective_cpp: string | null;
  total_cash_cost_twd: string;
  points_acquired: string;
  points_consumed: string;
  points_leftover: string;
};

export async function listPrograms(): Promise<Program[]> {
  return requestJson<Program[]>("/wallet/programs");
}

export async function createProgram(payload: { name: string; kind: string; expiry_rule_note?: string }): Promise<Program> {
  return requestJson<Program>("/wallet/programs", { method: "POST", body: JSON.stringify(payload) });
}

export async function listAccounts(): Promise<Account[]> {
  return requestJson<Account[]>("/wallet/accounts");
}

export async function createAccount(payload: {
  owner: string;
  program_id: number;
  account_ref?: string;
  notes?: string;
}): Promise<Account> {
  return requestJson<Account>("/wallet/accounts", { method: "POST", body: JSON.stringify(payload) });
}

export async function createLedger(payload: {
  account_id: number;
  kind: string;
  quantity: string;
  occurred_at: string;
  cost_total?: string | null;
  cost_currency?: string | null;
  note?: string;
  create_lot?: boolean;
}): Promise<LedgerTransaction> {
  return requestJson<LedgerTransaction>("/wallet/ledger", { method: "POST", body: JSON.stringify(payload) });
}

export async function listTransferRules(): Promise<TransferRule[]> {
  return requestJson<TransferRule[]>("/wallet/transfer-rules");
}

export async function createTransferRule(payload: {
  from_program_id: number;
  to_program_id: number;
  ratio_from: string;
  ratio_to: string;
  bonus_pct?: string;
  min_transfer?: string;
  valid_from: string;
  valid_until?: string;
  transfer_days_note?: string;
  rule_kind?: string;
  block_size?: string;
  block_bonus_points?: string;
}): Promise<TransferRule> {
  return requestJson<TransferRule>("/wallet/transfer-rules", { method: "POST", body: JSON.stringify(payload) });
}

export async function listPurchaseOffers(): Promise<PurchaseOffer[]> {
  return requestJson<PurchaseOffer[]>("/wallet/purchase-offers");
}

export async function createPurchaseOffer(payload: {
  program_id: number;
  kind: string;
  base_price: string;
  currency: string;
  bonus_pct?: string;
  min_points?: string;
  max_points?: string;
  start_date: string;
  end_date?: string;
  source_note?: string;
  paid_amount?: string;
  fees?: string;
  rebate?: string;
  points_received?: string;
}): Promise<PurchaseOffer> {
  return requestJson<PurchaseOffer>("/wallet/purchase-offers", { method: "POST", body: JSON.stringify(payload) });
}

export async function getPortfolio(owner?: string): Promise<Portfolio> {
  return requestJson<Portfolio>(`/wallet/portfolio${owner ? `?owner=${encodeURIComponent(owner)}` : ""}`);
}

export async function refreshFxRates(): Promise<{ source: string; created: string }> {
  return requestJson<{ source: string; created: string }>("/wallet/fx-rates/refresh", { method: "POST" });
}

export async function listAwardQuotes(): Promise<AwardQuote[]> {
  return requestJson<AwardQuote[]>("/wallet/award-quotes");
}

export async function createAwardQuote(payload: {
  origin?: string;
  destination?: string;
  travel_date?: string;
  cabin?: string;
  pax: number;
  program_id: number;
  miles_required: string;
  taxes_amount?: string | null;
  taxes_currency?: string | null;
  cash_price_twd?: string | null;
  source?: string;
}): Promise<AwardQuote> {
  return requestJson<AwardQuote>("/wallet/award-quotes", { method: "POST", body: JSON.stringify(payload) });
}

export async function evaluateAwardQuote(quoteId: number, evaluationDate?: string): Promise<FundingScenario[]> {
  return requestJson<FundingScenario[]>(`/wallet/award-quotes/${quoteId}/evaluate`, {
    method: "POST",
    body: JSON.stringify({ evaluation_date: evaluationDate || null }),
  });
}

export async function listFundingScenarios(quoteId: number): Promise<FundingScenario[]> {
  return requestJson<FundingScenario[]>(`/wallet/award-quotes/${quoteId}/scenarios`);
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
    let message = `請求失敗（狀態 ${response.status}）`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Keep generic status message.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}
