"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ImportBatch,
  RealizedTrade,
  TradeAttributionMetrics,
  TradeImportResponse,
  getTradeAttribution,
  listRealizedTrades,
  listTradeImports,
  uploadTradeHistory,
} from "../../../lib/capitalApi";
import styles from "./HistoryPage.module.css";

export default function CapitalHistoryPage() {
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [trades, setTrades] = useState<RealizedTrade[]>([]);
  const [metrics, setMetrics] = useState<TradeAttributionMetrics | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [lastImport, setLastImport] = useState<TradeImportResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadHistory();
  }, []);

  async function loadHistory() {
    setIsLoading(true);
    try {
      const [nextBatches, nextTrades, nextMetrics] = await Promise.all([
        listTradeImports(),
        listRealizedTrades(),
        getTradeAttribution(),
      ]);
      setBatches(nextBatches);
      setTrades(nextTrades);
      setMetrics(nextMetrics);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to load trade history.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUpload() {
    if (!selectedFile) return;
    setIsUploading(true);
    try {
      const result = await uploadTradeHistory(selectedFile);
      setLastImport(result);
      setSelectedFile(null);
      await loadHistory();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to import trade history.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>Capital History</span>
        </nav>

        <section className="page-header">
          <div>
            <div className="section-kicker">Capital</div>
            <h1>Trade History</h1>
            <p>Import synthetic-safe broker history, inspect FIFO realized trades, and review deterministic loss attribution.</p>
          </div>
          <Link className="button" href="/capital/decisions">
            Decisions
          </Link>
        </section>

        <section className="form-panel">
          <h2>Schwab CSV Import</h2>
          <label>
            <span>Statement CSV</span>
            <input accept=".csv,text/csv" type="file" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} />
          </label>
          <div className="form-actions">
            <button className="button button-primary" disabled={!selectedFile || isUploading} onClick={handleUpload} type="button">
              {isUploading ? "Importing..." : "Import"}
            </button>
            <button className="button" disabled={isLoading} onClick={loadHistory} type="button">
              Refresh
            </button>
          </div>
          {lastImport ? (
            <p className="subtle">
              Batch #{lastImport.batch_id}: {lastImport.created ? "created" : "already imported"} · fills {lastImport.fill_count} · warnings {lastImport.warning_count}
            </p>
          ) : null}
          {error ? <div className="notice notice-error">{error}</div> : null}
        </section>

        {isLoading ? (
          <section className="panel">
            <div className="loading-block" />
            <div className="loading-block short" />
          </section>
        ) : (
          <>
            {metrics ? <MetricsPanel metrics={metrics} /> : null}
            <BatchPanel batches={batches} />
            <RealizedTradesPanel trades={trades} />
          </>
        )}
      </div>
    </main>
  );
}

function MetricsPanel({ metrics }: { metrics: TradeAttributionMetrics }) {
  return (
    <section className="panel">
      <div className="stage-header">
        <h2>Loss Attribution</h2>
        <span className="stage-pill">{metrics.narrative.llm_backed ? "LLM-backed" : "narrative fallback"}</span>
      </div>
      <DataGrid
        items={[
          ["Trades", String(metrics.trade_count)],
          ["Gross P&L", metrics.gross_pnl],
          ["Win rate", `${Math.round(metrics.win_rate * 100)}%`],
          ["Expectancy", metrics.expectancy],
          ["Max consecutive losses", String(metrics.max_consecutive_losses)],
          ["Leveraged symbols", metrics.leveraged_symbols.join(", ") || "none"],
        ]}
      />
      <p className="subtle">{metrics.narrative.text}</p>
      <Table
        columns={["Symbol", "Trades", "Gross P&L", "Fees by month"]}
        rows={metrics.by_symbol.map((row) => [
          String(row.key),
          String(row.count),
          String(row.gross_pnl),
          formatRecord(row.fees_by_month),
        ])}
      />
      <div className={styles.historyGrid}>
        <MetricTable title="By Direction" rows={metrics.by_direction} />
        <MetricTable title="By Instrument" rows={metrics.by_instrument_type} />
        <MetricTable title="By Holding Period" rows={metrics.by_holding_period} />
        <MetricTable title="By Entry Weekday" rows={metrics.by_entry_weekday} />
        <MetricTable title="By Entry Hour" rows={metrics.by_entry_hour} />
      </div>
    </section>
  );
}

function MetricTable({ title, rows }: { title: string; rows: Array<Record<string, unknown>> }) {
  return (
    <div className={styles.miniPanel}>
      <h3>{title}</h3>
      <Table
        columns={["Bucket", "Trades", "Gross P&L"]}
        rows={rows.map((row) => [String(row.key), String(row.count), String(row.gross_pnl)])}
      />
    </div>
  );
}

function BatchPanel({ batches }: { batches: ImportBatch[] }) {
  return (
    <section className="panel">
      <h2>Import Batches</h2>
      <Table
        columns={["ID", "Source", "Fills", "Cash rows", "Warnings", "Imported"]}
        rows={batches.map((batch) => [
          String(batch.id),
          batch.source,
          String(batch.fill_count),
          String(batch.cash_row_count),
          String(batch.warning_count),
          formatDate(batch.imported_at),
        ])}
      />
    </section>
  );
}

function RealizedTradesPanel({ trades }: { trades: RealizedTrade[] }) {
  return (
    <section className="panel">
      <h2>Realized Trades</h2>
      <Table
        columns={["Symbol", "Direction", "Quantity", "Entry", "Exit", "Gross P&L", "Closed"]}
        rows={trades.map((trade) => [
          trade.symbol,
          trade.direction,
          trade.quantity,
          trade.avg_entry,
          trade.avg_exit,
          `${trade.gross_pnl} ${trade.currency}`,
          trade.closed_at ? formatDate(trade.closed_at) : "unknown",
        ])}
      />
    </section>
  );
}

function DataGrid({ items }: { items: Array<[string, string]> }) {
  return (
    <dl className="data-grid">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Table({ columns, rows }: { columns: string[]; rows: string[][] }) {
  if (rows.length === 0) {
    return <p className="pending-text">No records yet</p>;
  }
  return (
    <div className={styles.tableWrap}>
      <table className={styles.historyTable}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.join("-")}-${index}`}>
              {row.map((cell, cellIndex) => (
                <td key={`${cell}-${cellIndex}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatRecord(value: unknown): string {
  if (!value || typeof value !== "object") {
    return "none";
  }
  return Object.entries(value as Record<string, unknown>)
    .map(([key, entry]) => `${key}: ${String(entry)}`)
    .join("; ");
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}
