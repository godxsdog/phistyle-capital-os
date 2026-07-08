const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type FlightStatusResult = {
  flight_no: string;
  flight_date: string;
  status: string | null;
  display: string;
  raw: Record<string, unknown>;
};

export type ToolMonitorSettings = {
  id: number;
  kind: string;
  enabled: boolean;
  flight_no: string;
  flight_date: string;
  interval_minutes: number;
  last_run_at: string | null;
  last_status_ok: boolean | null;
  last_status_display: string | null;
  last_status_fail_count: number;
  updated_at: string;
};

export type MonitorTickResult = {
  skipped: boolean;
  reason: string | null;
  ran_at: string | null;
  status_ok: boolean | null;
  display: string | null;
  notified: boolean;
};

export async function getFlightWatchSettings(): Promise<ToolMonitorSettings> {
  return requestJson<ToolMonitorSettings>("/tools/monitors/flight_watch");
}

export async function updateFlightWatchSettings(payload: {
  enabled?: boolean;
  flight_no?: string;
  flight_date?: string;
  interval_minutes?: number;
}): Promise<ToolMonitorSettings> {
  return requestJson<ToolMonitorSettings>("/tools/monitors/flight_watch", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function queryFlightStatus(flightNo: string, flightDate: string): Promise<FlightStatusResult> {
  return requestJson<FlightStatusResult>("/tools/flight-status", {
    method: "POST",
    body: JSON.stringify({ flight_no: flightNo, flight_date: flightDate }),
  });
}

export async function tickFlightWatchMonitor(): Promise<MonitorTickResult> {
  return requestJson<MonitorTickResult>("/tools/monitors/tick", { method: "POST" });
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
      if (typeof payload.detail === "string") message = payload.detail;
    } catch {
      // Keep the generic HTTP message.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}
