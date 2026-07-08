"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  FlightStatusResult,
  ToolMonitorSettings,
  getFlightWatchSettings,
  queryFlightStatus,
  tickFlightWatchMonitor,
  updateFlightWatchSettings,
} from "../../lib/toolsApi";
import styles from "./ToolsPage.module.css";

const STORAGE_KEY = "phistyle.tools.flightWatch";
const DEFAULT_FLIGHT_NO = "AK1511";
const DEFAULT_FLIGHT_DATE = "2026-07-10";
const INTERVAL_OPTIONS = [10, 20, 30, 60];

type StoredFlightPrefs = {
  flightNo: string;
  flightDate: string;
};

export default function ToolsPage() {
  const [flightNo, setFlightNo] = useState(DEFAULT_FLIGHT_NO);
  const [flightDate, setFlightDate] = useState(DEFAULT_FLIGHT_DATE);
  const [result, setResult] = useState<FlightStatusResult | null>(null);
  const [querying, setQuerying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [settings, setSettings] = useState<ToolMonitorSettings | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [savingSettings, setSavingSettings] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<StoredFlightPrefs>;
        if (parsed.flightNo) setFlightNo(parsed.flightNo);
        if (parsed.flightDate) setFlightDate(parsed.flightDate);
      }
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    void loadSettings();
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ flightNo, flightDate }));
  }, [flightNo, flightDate]);

  async function loadSettings() {
    try {
      const next = await getFlightWatchSettings();
      setSettings(next);
      setSettingsError(null);
    } catch (err: unknown) {
      setSettingsError(err instanceof Error ? err.message : "讀取監控設定失敗。");
    }
  }

  async function query() {
    setQuerying(true);
    setError(null);
    try {
      const next = await queryFlightStatus(flightNo.trim().toUpperCase(), flightDate);
      setResult(next);
    } catch (err: unknown) {
      setResult(null);
      setError(err instanceof Error ? err.message : "查詢航班狀態失敗。");
    } finally {
      setQuerying(false);
    }
  }

  async function toggleMonitor(enabled: boolean) {
    setSavingSettings(true);
    try {
      const next = await updateFlightWatchSettings({ enabled, flight_no: flightNo.trim().toUpperCase(), flight_date: flightDate });
      setSettings(next);
      setSettingsError(null);
    } catch (err: unknown) {
      setSettingsError(err instanceof Error ? err.message : "更新監控設定失敗。");
    } finally {
      setSavingSettings(false);
    }
  }

  async function updateInterval(intervalMinutes: number) {
    setSavingSettings(true);
    try {
      const next = await updateFlightWatchSettings({ interval_minutes: intervalMinutes });
      setSettings(next);
      setSettingsError(null);
    } catch (err: unknown) {
      setSettingsError(err instanceof Error ? err.message : "更新監控設定失敗。");
    } finally {
      setSavingSettings(false);
    }
  }

  async function runTickNow() {
    setSavingSettings(true);
    try {
      await tickFlightWatchMonitor();
      await loadSettings();
      setSettingsError(null);
    } catch (err: unknown) {
      setSettingsError(err instanceof Error ? err.message : "執行監控失敗。");
    } finally {
      setSavingSettings(false);
    }
  }

  const statusClass = result
    ? result.status === "cancelled" || result.status === "not_listed"
      ? styles.statusBad
      : result.status === "delayed" || result.status === "time_changed"
        ? styles.statusWarn
        : styles.statusOk
    : "";

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>工具</span>
        </nav>

        <section className="page-header">
          <div>
            <div className="section-kicker">工具</div>
            <h1>工具箱</h1>
            <p>手動查詢與自動監控放在同一頁；監控只做記錄與 Telegram 提醒，不會自動處理任何事。</p>
          </div>
        </section>

        <section className="panel">
          <h2>✈️ 航班狀態</h2>
          <div className={styles.fieldRow}>
            <label>
              <span>航班編號</span>
              <input value={flightNo} onChange={(event) => setFlightNo(event.target.value.toUpperCase())} placeholder="AK1511" />
            </label>
            <label>
              <span>日期</span>
              <input type="date" value={flightDate} onChange={(event) => setFlightDate(event.target.value)} />
            </label>
          </div>
          <div className="form-actions">
            <button className="button button-primary" type="button" disabled={querying} onClick={() => void query()}>
              {querying ? "查詢中…" : "查詢"}
            </button>
          </div>
          {error ? <div className="notice notice-error">{error}</div> : null}
          {result ? (
            <div className={`${styles.statusDisplay} ${statusClass}`}>
              {result.display}
            </div>
          ) : null}
        </section>

        <section className="panel">
          <div className="stage-header">
            <h2>自動監控</h2>
            <span className="stage-pill">Mac mini 排程觸發 /tools/monitors/tick</span>
          </div>
          <label className={styles.checkboxLine}>
            <input
              type="checkbox"
              checked={settings?.enabled ?? false}
              disabled={savingSettings}
              onChange={(event) => void toggleMonitor(event.target.checked)}
            />
            <span>☑️ 啟用自動監控</span>
          </label>
          <label>
            <span>檢查間隔</span>
            <select
              value={settings?.interval_minutes ?? 30}
              disabled={savingSettings}
              onChange={(event) => void updateInterval(Number(event.target.value))}
            >
              {INTERVAL_OPTIONS.map((minutes) => (
                <option key={minutes} value={minutes}>{minutes} 分鐘</option>
              ))}
            </select>
          </label>
          <div className="form-actions">
            <button className="button" type="button" disabled={savingSettings} onClick={() => void runTickNow()}>
              立即檢查一次
            </button>
          </div>
          {settingsError ? <div className="notice notice-error">{settingsError}</div> : null}
          {settings ? (
            <p className={styles.metaLine}>
              上次執行：{settings.last_run_at ? formatDateTime(settings.last_run_at) : "尚未執行"}
              {" ・ "}
              上次狀態：{settings.last_status_display || "尚無資料"}
              {settings.last_status_fail_count > 0 ? `（連續失敗 ${settings.last_status_fail_count} 次）` : ""}
            </p>
          ) : null}
        </section>
      </div>
    </main>
  );
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-TW", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}
