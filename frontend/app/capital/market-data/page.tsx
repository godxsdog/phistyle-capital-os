"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader, StatusChip } from "../../../components/ui";
import {
  MarketIngestRun,
  MarketSanityRow,
  MarketWatchlistSymbol,
  createMarketWatchlistSymbol,
  deleteMarketWatchlistSymbol,
  listMarketIngestRuns,
  listMarketSanity,
  listMarketWatchlist,
  runMarketIngest,
  updateMarketWatchlistSymbol,
} from "../../../lib/capitalApi";
import { MARKET_LABELS, SOURCE_LABELS, formatDateTimeZh, labelFor } from "../../../lib/displayConstants";
import styles from "./MarketDataPage.module.css";

export default function CapitalMarketDataPage() {
  const [watchlist, setWatchlist] = useState<MarketWatchlistSymbol[]>([]);
  const [sanity, setSanity] = useState<MarketSanityRow[]>([]);
  const [runs, setRuns] = useState<MarketIngestRun[]>([]);
  const [symbol, setSymbol] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setIsLoading(true);
    try {
      const [nextWatchlist, nextSanity, nextRuns] = await Promise.all([
        listMarketWatchlist(),
        listMarketSanity(),
        listMarketIngestRuns(),
      ]);
      setWatchlist(nextWatchlist);
      setSanity(nextSanity);
      setRuns(nextRuns);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "讀取市場資料失敗。");
    } finally {
      setIsLoading(false);
    }
  }

  async function addSymbol() {
    if (!symbol.trim()) return;
    try {
      const created = await createMarketWatchlistSymbol(symbol.trim());
      setSymbol("");
      setMessage(`已加入 ${created.symbol}`);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "加入觀察清單失敗。");
    }
  }

  async function toggleSymbol(row: MarketWatchlistSymbol) {
    try {
      await updateMarketWatchlistSymbol(row.id, row.symbol, !row.active);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "更新觀察清單失敗。");
    }
  }

  async function removeSymbol(row: MarketWatchlistSymbol) {
    try {
      await deleteMarketWatchlistSymbol(row.id);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "刪除觀察清單失敗。");
    }
  }

  async function ingest(source: "taifex" | "yahoo" | "all") {
    setMessage(null);
    try {
      const result = await runMarketIngest(source);
      setMessage(result.results.map((row) => `${labelFor(SOURCE_LABELS, row.source)}：新增 ${row.inserted}、略過 ${row.skipped}、警告 ${row.warnings.length}`).join("；"));
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "匯入市場資料失敗。");
    }
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="麵包屑">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>市場資料</span>
        </nav>

        <PageHeader
          kicker="Capital"
          title="市場資料健康表"
          description="管理美股觀察清單、手動匯入 TAIFEX 與 Yahoo 日 K，並檢查資料缺口與修正警告。"
          actions={<Link className="button" href="/capital/history">交易紀錄</Link>}
        />

        <section className="form-panel">
          <h2>美股觀察清單</h2>
          <div className={styles.fieldRow}>
            <label>
              <span>美股代號</span>
              <input value={symbol} placeholder="AAPL" onChange={(event) => setSymbol(event.target.value)} />
            </label>
            <button className="button button-primary" type="button" onClick={addSymbol}>加入</button>
          </div>
          <p className="subtle">Yahoo 端點使用 10 年日 K；代號會以大寫儲存，抓取時直接送 Yahoo 原始 symbol。</p>
          <WatchlistTable rows={watchlist} onToggle={toggleSymbol} onDelete={removeSymbol} />
        </section>

        <section className="panel">
          <div className="stage-header">
            <h2>手動匯入</h2>
            <span className="stage-pill">排程由 Mac mini cron 執行</span>
          </div>
          <div className={styles.toolbar}>
            <button className="button" type="button" onClick={() => void ingest("taifex")}>匯入 TAIFEX</button>
            <button className="button" type="button" onClick={() => void ingest("yahoo")}>匯入 Yahoo</button>
            <button className="button button-primary" type="button" onClick={() => void ingest("all")}>全部匯入</button>
            <button className="button" type="button" disabled={isLoading} onClick={() => void loadAll()}>重新整理</button>
          </div>
          {message ? <div className="notice">{message}</div> : null}
          {error ? <div className="notice notice-error">{error}</div> : null}
        </section>

        <section className="panel">
          <h2>資料健康</h2>
          <SanityTable rows={sanity} />
        </section>

        <section className="panel">
          <h2>匯入紀錄</h2>
          <RunsTable rows={runs} />
        </section>
      </div>
    </main>
  );
}

function WatchlistTable({ rows, onToggle, onDelete }: { rows: MarketWatchlistSymbol[]; onToggle: (row: MarketWatchlistSymbol) => void; onDelete: (row: MarketWatchlistSymbol) => void }) {
  if (rows.length === 0) return <p className="pending-text">尚未加入美股觀察清單</p>;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead><tr><th>市場</th><th>代號</th><th>狀態</th><th>操作</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{labelFor(MARKET_LABELS, row.market)}</td>
              <td>{row.symbol}</td>
              <td><StatusChip value={row.active ? "active" : "inactive"} /></td>
              <td>
                <div className={styles.rowActions}>
                  <button className="button" type="button" onClick={() => onToggle(row)}>{row.active ? "停用" : "啟用"}</button>
                  <button className="button button-danger" type="button" onClick={() => onDelete(row)}>刪除</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SanityTable({ rows }: { rows: MarketSanityRow[] }) {
  if (rows.length === 0) return <p className="pending-text">尚無日 K 資料</p>;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead><tr><th>市場</th><th>代號</th><th>起始</th><th>最新</th><th>筆數</th><th>缺口</th><th>備註</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.market}-${row.symbol}`}>
              <td>{labelFor(MARKET_LABELS, row.market)}</td>
              <td>{row.symbol}</td>
              <td>{row.first_date || "-"}</td>
              <td>{row.last_date || "-"}</td>
              <td>{row.row_count}</td>
              <td className={row.gap_count ? styles.statusWarn : styles.statusOk}>{row.gap_count}</td>
              <td>{row.note || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunsTable({ rows }: { rows: MarketIngestRun[] }) {
  if (rows.length === 0) return <p className="pending-text">尚無匯入紀錄</p>;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead><tr><th>來源</th><th>日期</th><th>狀態</th><th>內容</th><th>完成時間</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{labelFor(SOURCE_LABELS, row.source)}</td>
              <td>{row.run_date}</td>
              <td><StatusChip value={row.status} /></td>
              <td>{row.detail || "-"}</td>
              <td>{formatDateTimeZh(row.finished_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
