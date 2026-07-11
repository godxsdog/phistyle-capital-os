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
  source_url: string | null;
};

export type WalletAiParsedRule = {
  from_program_name: string | null;
  to_program_name: string | null;
  ratio_from: string | null;
  ratio_to: string | null;
  bonus_pct: string | null;
  min_transfer: string | null;
  rule_kind: string | null;
  block_size: string | null;
  block_bonus_points: string | null;
  valid_until: string | null;
  source_url: string | null;
  note: string | null;
};

export type WalletAiParseRuleResponse = {
  status: "preview" | "failed" | string;
  preview: WalletAiParsedRule | null;
  message: string;
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
  source_url: string | null;
};

export type FxRate = {
  id: number;
  currency: string;
  twd_per_unit: string;
  as_of: string;
  source: string;
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
  note: string | null;
  created_at: string;
};

export type TripQuest = {
  id: number;
  origin: string;
  destination: string;
  programs: string[];
  window_start: string;
  window_end: string;
  trip_days: number;
  cabin: string;
  pax: number;
  created_at: string;
};

export type QuestResult = {
  id: number;
  trip_quest_id: number;
  run_date: string;
  rank: number;
  program: string;
  outbound_date: string;
  return_date: string;
  outbound_miles: string;
  return_miles: string;
  total_miles: string;
  outbound_taxes: string | null;
  return_taxes: string | null;
  seats_min: number;
  raw_refs: string | null;
};

export type TripQuestRunResponse = {
  quest: TripQuest;
  results: QuestResult[];
  created_results: number;
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

export type AwardWatch = {
  id: number;
  origin: string;
  destination: string;
  cabin: string;
  start_date: string | null;
  end_date: string | null;
  program_id: number | null;
  active: boolean;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export type AwardSnapshot = {
  id: number;
  watch_id: number;
  seen_date: string;
  status: string;
  result_count: number;
  normalized_json: string;
  created_at: string;
};

export type ExpiryAlert = {
  id: number;
  account_id: number | null;
  voucher_id: number | null;
  threshold_days: number;
  expires_at: string;
  checked_on: string;
  balance: string;
  status: string;
  message: string;
  created_at: string;
};

export type HotelVoucher = {
  id: number;
  owner: "kent" | "wife" | string;
  program_id: number;
  program_name: string;
  face_value_points: string;
  expires_at: string;
  status: "active" | "used" | "expired" | string;
  acquired_note: string | null;
  used_note: string | null;
  created_at: string;
};

export type HotelStayQuote = {
  id: number;
  owner: "kent" | "wife" | string;
  hotel_name: string;
  stay_date: string;
  nights: number;
  program_id: number;
  program_name: string;
  cash_price_twd: string;
  points_price_per_night: string;
  taxes_note: string | null;
  topup_allowed: boolean;
  topup_points: string | null;
  created_at: string;
};

export type HotelStayOption = {
  method: "cash" | "points" | "voucher" | "voucher_topup" | string;
  label: string;
  available: boolean;
  cash_cost_twd: string | null;
  rank: number | null;
  notes: string[];
  voucher_ids: number[];
  nights_with_voucher: number;
  nights_with_points: number;
  points_consumed: string;
  lots_consumed?: Array<Record<string, string | number>>;
};

export type HotelStayEvaluation = {
  quote: HotelStayQuote;
  cpp: string;
  total_points: string;
  options: HotelStayOption[];
  notes: string[];
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
  source_url?: string;
}): Promise<TransferRule> {
  return requestJson<TransferRule>("/wallet/transfer-rules", { method: "POST", body: JSON.stringify(payload) });
}

export async function updateTransferRule(id: number, payload: {
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
  source_url?: string;
}): Promise<TransferRule> {
  return requestJson<TransferRule>(`/wallet/transfer-rules/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function deleteTransferRule(id: number): Promise<{ status: string }> {
  return requestJson<{ status: string }>(`/wallet/transfer-rules/${id}`, { method: "DELETE" });
}

export async function parseWalletRuleWithAi(payload: {
  source_program_name: string;
  pasted_text: string;
}): Promise<WalletAiParseRuleResponse> {
  return requestJson<WalletAiParseRuleResponse>("/wallet/ai-parse-rule", { method: "POST", body: JSON.stringify(payload) });
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
  source_url?: string;
}): Promise<PurchaseOffer> {
  return requestJson<PurchaseOffer>("/wallet/purchase-offers", { method: "POST", body: JSON.stringify(payload) });
}

export async function getPortfolio(owner?: string): Promise<Portfolio> {
  return requestJson<Portfolio>(`/wallet/portfolio${owner ? `?owner=${encodeURIComponent(owner)}` : ""}`);
}

export async function listHotelVouchers(): Promise<HotelVoucher[]> {
  return requestJson<HotelVoucher[]>("/wallet/hotel-vouchers");
}

export async function createHotelVoucher(payload: {
  owner: string;
  program_id: number;
  face_value_points: string;
  expires_at: string;
  acquired_note?: string | null;
}): Promise<HotelVoucher> {
  return requestJson<HotelVoucher>("/wallet/hotel-vouchers", { method: "POST", body: JSON.stringify(payload) });
}

export async function updateHotelVoucherStatus(id: number, payload: {
  status: "used" | "expired";
  used_note?: string | null;
}): Promise<HotelVoucher> {
  return requestJson<HotelVoucher>(`/wallet/hotel-vouchers/${id}/status`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function listHotelStayQuotes(): Promise<HotelStayQuote[]> {
  return requestJson<HotelStayQuote[]>("/wallet/hotel-stay-quotes");
}

export async function createHotelStayQuote(payload: {
  owner: string;
  hotel_name: string;
  stay_date: string;
  nights: number;
  program_id: number;
  cash_price_twd: string;
  points_price_per_night: string;
  taxes_note?: string | null;
  topup_allowed: boolean;
  topup_points?: string | null;
}): Promise<HotelStayQuote> {
  return requestJson<HotelStayQuote>("/wallet/hotel-stay-quotes", { method: "POST", body: JSON.stringify(payload) });
}

export async function evaluateHotelStayQuote(quoteId: number): Promise<HotelStayEvaluation> {
  return requestJson<HotelStayEvaluation>(`/wallet/hotel-stay-quotes/${quoteId}/evaluate`, { method: "POST" });
}

export async function refreshFxRates(): Promise<{ source: string; created: string }> {
  return requestJson<{ source: string; created: string }>("/wallet/fx-rates/refresh", { method: "POST" });
}

export async function listFxRates(): Promise<FxRate[]> {
  return requestJson<FxRate[]>("/wallet/fx-rates");
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
  note?: string | null;
}): Promise<AwardQuote> {
  return requestJson<AwardQuote>("/wallet/award-quotes", { method: "POST", body: JSON.stringify(payload) });
}

export async function listTripQuests(): Promise<TripQuest[]> {
  return requestJson<TripQuest[]>("/wallet/trip-quests");
}

export async function runTripQuest(payload: {
  origin: string;
  destination: string;
  programs: string[];
  window_start: string;
  window_end: string;
  trip_days: number;
  cabin: string;
  pax: number;
}): Promise<TripQuestRunResponse> {
  return requestJson<TripQuestRunResponse>("/wallet/trip-quests/run", { method: "POST", body: JSON.stringify(payload) });
}

export async function listQuestResults(questId: number): Promise<QuestResult[]> {
  return requestJson<QuestResult[]>(`/wallet/trip-quests/${questId}/results`);
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

export async function listAwardWatches(): Promise<AwardWatch[]> {
  return requestJson<AwardWatch[]>("/wallet/award-watches");
}

export async function createAwardWatch(payload: {
  origin: string;
  destination: string;
  cabin: string;
  start_date?: string | null;
  end_date?: string | null;
  program_id?: number | null;
  active?: boolean;
  note?: string | null;
}): Promise<AwardWatch> {
  return requestJson<AwardWatch>("/wallet/award-watches", { method: "POST", body: JSON.stringify(payload) });
}

export async function updateAwardWatch(id: number, payload: {
  origin: string;
  destination: string;
  cabin: string;
  start_date?: string | null;
  end_date?: string | null;
  program_id?: number | null;
  active?: boolean;
  note?: string | null;
}): Promise<AwardWatch> {
  return requestJson<AwardWatch>(`/wallet/award-watches/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function deleteAwardWatch(id: number): Promise<{ status: string }> {
  return requestJson<{ status: string }>(`/wallet/award-watches/${id}`, { method: "DELETE" });
}

export async function fetchAwardWatch(watchId: number, seenDate?: string): Promise<AwardSnapshot> {
  return requestJson<AwardSnapshot>(`/wallet/award-watches/${watchId}/fetch`, {
    method: "POST",
    body: JSON.stringify({ seen_date: seenDate || null }),
  });
}

export async function listAwardSnapshots(watchId?: number): Promise<AwardSnapshot[]> {
  return requestJson<AwardSnapshot[]>(`/wallet/award-snapshots${watchId ? `?watch_id=${watchId}` : ""}`);
}

export async function promoteAwardSnapshot(snapshotId: number, itemIndex = 0): Promise<{ award_quote: AwardQuote }> {
  return requestJson<{ award_quote: AwardQuote }>(`/wallet/award-snapshots/${snapshotId}/promote`, {
    method: "POST",
    body: JSON.stringify({ item_index: itemIndex }),
  });
}

export async function listExpiryAlerts(): Promise<ExpiryAlert[]> {
  return requestJson<ExpiryAlert[]>("/wallet/expiry-alerts");
}

export async function scanExpiryAlerts(): Promise<ExpiryAlert[]> {
  return requestJson<ExpiryAlert[]>("/wallet/expiry-alerts/scan", { method: "POST" });
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
