const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type LoyaltyProgram = {
  id: number;
  name: string;
  kind: string;
  notes: string | null;
};

export type PointBalance = {
  id: number;
  program_id: number;
  balance: string;
  as_of: string;
  expires_at: string | null;
  note: string | null;
  created_at: string | null;
};

export type ValuationRate = {
  id: number;
  program_id: number;
  twd_per_point: string;
  effective_date: string;
  source: string | null;
};

export type TransferPartner = {
  id: number;
  from_program_id: number;
  to_program_id: number;
  ratio_from: number;
  ratio_to: number;
  transfer_days: string | null;
  notes: string | null;
};

export type AwardWatch = {
  id: number;
  origin: string;
  destination: string;
  cabin: string;
  program_id: number | null;
  active: boolean;
};

export type AwardAvailability = {
  id: number;
  watch_id: number;
  seen_date: string;
  flight_date: string;
  program: string;
  seats: number | null;
  miles_cost: string | null;
  taxes_fees: string | null;
  source: string;
  raw: string | null;
};

export type WalletPortfolio = {
  total_value_twd: string;
  programs: Array<Record<string, string | number | null>>;
  expiring_soon: Array<Record<string, string | number | null>>;
};

export async function seedWalletDefaults(): Promise<void> {
  await requestJson("/wallet/seed-defaults", { method: "POST" });
}

export async function listPrograms(): Promise<LoyaltyProgram[]> {
  return requestJson<LoyaltyProgram[]>("/wallet/programs");
}

export async function createProgram(payload: { name: string; kind: string; notes?: string }): Promise<LoyaltyProgram> {
  return requestJson<LoyaltyProgram>("/wallet/programs", { method: "POST", body: JSON.stringify(payload) });
}

export async function listBalances(): Promise<PointBalance[]> {
  return requestJson<PointBalance[]>("/wallet/balances");
}

export async function createBalance(payload: {
  program_id: number;
  balance: string;
  as_of: string;
  expires_at?: string | null;
  note?: string;
}): Promise<PointBalance> {
  return requestJson<PointBalance>("/wallet/balances", { method: "POST", body: JSON.stringify(payload) });
}

export async function listValuations(): Promise<ValuationRate[]> {
  return requestJson<ValuationRate[]>("/wallet/valuations");
}

export async function createValuation(payload: {
  program_id: number;
  twd_per_point: string;
  effective_date: string;
  source?: string;
}): Promise<ValuationRate> {
  return requestJson<ValuationRate>("/wallet/valuations", { method: "POST", body: JSON.stringify(payload) });
}

export async function listTransfers(): Promise<TransferPartner[]> {
  return requestJson<TransferPartner[]>("/wallet/transfers");
}

export async function createTransfer(payload: {
  from_program_id: number;
  to_program_id: number;
  ratio_from: number;
  ratio_to: number;
  transfer_days?: string;
  notes?: string;
}): Promise<TransferPartner> {
  return requestJson<TransferPartner>("/wallet/transfers", { method: "POST", body: JSON.stringify(payload) });
}

export async function listWatches(): Promise<AwardWatch[]> {
  return requestJson<AwardWatch[]>("/wallet/watches");
}

export async function createWatch(payload: {
  origin: string;
  destination: string;
  cabin: string;
  program_id?: number | null;
}): Promise<AwardWatch> {
  return requestJson<AwardWatch>("/wallet/watches", { method: "POST", body: JSON.stringify(payload) });
}

export async function fetchWatch(watchId: number): Promise<{ created: number }> {
  return requestJson<{ created: number }>(`/wallet/watches/${watchId}/fetch`, { method: "POST" });
}

export async function listAvailability(): Promise<AwardAvailability[]> {
  return requestJson<AwardAvailability[]>("/wallet/availability");
}

export async function createAvailability(payload: {
  watch_id: number;
  seen_date: string;
  flight_date: string;
  program: string;
  seats?: number | null;
  miles_cost?: string | null;
  taxes_fees?: string;
  source: "manual";
}): Promise<AwardAvailability> {
  return requestJson<AwardAvailability>("/wallet/availability", { method: "POST", body: JSON.stringify(payload) });
}

export async function getPortfolio(): Promise<WalletPortfolio> {
  return requestJson<WalletPortfolio>("/wallet/portfolio");
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
