"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DataTable, PageHeader } from "../../../components/ui";
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
import { DIRECTION_LABELS, SOURCE_LABELS, formatDateTimeZh, labelFor } from "../../../lib/displayConstants";
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
      setError(err instanceof Error ? err.message : "讀取交易紀錄失敗。");
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
      setError(err instanceof Error ? err.message : "匯入交易紀錄失敗。");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="麵包屑">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>交易紀錄</span>
        </nav>

        <PageHeader
          kicker="Capital"
          title="交易紀錄"
          description="匯入券商 CSV、檢視 FIFO 已實現交易，並閱讀決定論虧損歸因。"
          actions={
            <Link className="button" href="/capital/decisions">
              交易決策
            </Link>
          }
        />

        <section className="form-panel">
          <h2>Schwab CSV 匯入</h2>
          <p className="subtle">上傳檔案只在記憶體處理，不會落地保存；真實對帳單不要提交到 repo。</p>
          <label>
            <span>對帳單 CSV</span>
            <input accept=".csv,text/csv" type="file" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} />
          </label>
          <div className="form-actions">
            <button className="button button-primary" disabled={!selectedFile || isUploading} onClick={handleUpload} type="button">
              {isUploading ? "匯入中..." : "匯入"}
            </button>
            <button className="button" disabled={isLoading} onClick={loadHistory} type="button">
              重新整理
            </button>
          </div>
          {lastImport ? (
            <p className="subtle">
              批次 #{lastImport.batch_id}：{lastImport.created ? "已建立" : "已匯入過"} · 成交 {lastImport.fill_count} · 警告 {lastImport.warning_count}
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
        <h2>虧損歸因</h2>
        <span className="stage-pill">{metrics.narrative.llm_backed ? "LLM 支援" : "規則敘事 fallback"}</span>
      </div>
      <DataGrid
        items={[
          ["交易數", String(metrics.trade_count)],
          ["總損益", metrics.gross_pnl],
          ["勝率", `${Math.round(metrics.win_rate * 100)}%`],
          ["期望值", metrics.expectancy],
          ["最大連續虧損", String(metrics.max_consecutive_losses)],
          ["槓桿標的", metrics.leveraged_symbols.join("、") || "無"],
        ]}
      />
      <p className="subtle">{metrics.narrative.text}</p>
      <DataTable
        columns={["標的", "交易數", "總損益", "月費用"]}
        rows={metrics.by_symbol.map((row) => [
          String(row.key),
          String(row.count),
          <PnlValue key={`${String(row.key)}-pnl`} value={String(row.gross_pnl)} />,
          formatRecord(row.fees_by_month),
        ])}
      />
      <div className={styles.historyGrid}>
        <MetricTable title="依方向" rows={metrics.by_direction} />
        <MetricTable title="依商品類型" rows={metrics.by_instrument_type} />
        <MetricTable title="依持有期間" rows={metrics.by_holding_period} />
        <MetricTable title="依進場星期" rows={metrics.by_entry_weekday} />
        <MetricTable title="依進場小時" rows={metrics.by_entry_hour} />
      </div>
    </section>
  );
}

function MetricTable({ title, rows }: { title: string; rows: Array<Record<string, unknown>> }) {
  return (
    <div className={styles.miniPanel}>
      <h3>{title}</h3>
      <DataTable
        columns={["分類", "交易數", "總損益"]}
        rows={rows.map((row) => [
          String(row.key),
          String(row.count),
          <PnlValue key={`${String(row.key)}-metric-pnl`} value={String(row.gross_pnl)} />,
        ])}
      />
    </div>
  );
}

function BatchPanel({ batches }: { batches: ImportBatch[] }) {
  return (
    <section className="panel">
      <h2>匯入批次</h2>
      <DataTable
        columns={["編號", "來源", "成交列", "現金列", "警告", "匯入時間"]}
        rows={batches.map((batch) => [
          `#${batch.id}`,
          labelFor(SOURCE_LABELS, batch.source),
          String(batch.fill_count),
          String(batch.cash_row_count),
          String(batch.warning_count),
          formatDateTimeZh(batch.imported_at),
        ])}
      />
    </section>
  );
}

function RealizedTradesPanel({ trades }: { trades: RealizedTrade[] }) {
  const groups = groupTradesByMonth(trades);
  return (
    <section className="panel">
      <div className="stage-header"><h2>已實現交易</h2><span className="stage-pill">券商對帳單</span></div>
      {groups.length === 0 ? <p className="pending-text">目前沒有已實現交易。</p> : null}
      <div className={styles.monthGroups}>
        {groups.map((group, index) => (
          <details className={styles.monthGroup} key={group.month} open={index === 0}>
            <summary>
              <span><strong>{monthLabel(group.month)}</strong><small>{group.trades.length} 筆交易</small></span>
              <span className={styles.monthSubtotal}>小計 <PnlValue value={String(group.subtotal)} suffix={group.currency} /></span>
            </summary>
            <DataTable
              columns={["標的", "方向", "數量", "進場均價", "出場均價", "總損益", "平倉時間"]}
              rows={group.trades.map((trade) => [
                <strong key={`${trade.id}-symbol`}>{trade.symbol}</strong>,
                labelFor(DIRECTION_LABELS, trade.direction),
                trade.quantity,
                trade.avg_entry,
                trade.avg_exit,
                <PnlValue key={`${trade.id}-trade-pnl`} value={trade.gross_pnl} suffix={trade.currency} />,
                trade.closed_at ? formatDateTimeZh(trade.closed_at) : "未知",
              ])}
            />
          </details>
        ))}
      </div>
    </section>
  );
}

function groupTradesByMonth(trades: RealizedTrade[]) {
  const groups = new Map<string, RealizedTrade[]>();
  for (const trade of trades) {
    const month = trade.closed_at ? trade.closed_at.slice(0, 7) : "unknown";
    groups.set(month, [...(groups.get(month) || []), trade]);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => right.localeCompare(left))
    .map(([month, monthTrades]) => ({
      month,
      trades: monthTrades,
      subtotal: monthTrades.reduce((sum, trade) => sum + Number(trade.gross_pnl || 0), 0),
      currency: monthTrades[0]?.currency || "",
    }));
}

function monthLabel(month: string): string {
  if (month === "unknown") return "日期未知";
  const [year, value] = month.split("-");
  return `${year} 年 ${Number(value)} 月`;
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

function formatRecord(value: unknown): string {
  if (!value || typeof value !== "object") {
    return "無";
  }
  return Object.entries(value as Record<string, unknown>)
    .map(([key, entry]) => `${key}: ${String(entry)}`)
    .join("; ");
}

function PnlValue({ value, suffix }: { value: string; suffix?: string }) {
  const numberValue = Number(value);
  const className = Number.isFinite(numberValue) && numberValue >= 0 ? "text-gain" : "text-loss";
  return <span className={className}>{value}{suffix ? ` ${suffix}` : ""}</span>;
}
