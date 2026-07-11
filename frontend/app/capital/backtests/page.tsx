"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { KpiCard, PageHeader } from "../../../components/ui";
import {
  BacktestRun,
  BacktestTrade,
  BacktestWindowResult,
  listBacktestRuns,
  runBacktest,
} from "../../../lib/capitalApi";
import styles from "./BacktestsPage.module.css";

const SAMPLE_SPEC = {
  name: "TX SMA 範例",
  market: "taifex",
  symbol: "TX",
  direction: "long",
  entry: { type: "sma_cross", fast: 2, slow: 3 },
  exit: { target_pct: 0.1, opposite_signal: false },
};

export default function CapitalBacktestsPage() {
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null);
  const [specText, setSpecText] = useState(JSON.stringify(SAMPLE_SPEC, null, 2));
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    void loadRuns();
  }, []);

  async function loadRuns() {
    setIsLoading(true);
    try {
      const nextRuns = await listBacktestRuns();
      setRuns(nextRuns);
      setSelectedRun((current) => current ?? nextRuns[0] ?? null);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "讀取回測紀錄失敗。");
    } finally {
      setIsLoading(false);
    }
  }

  async function submitRun() {
    setMessage(null);
    setError(null);
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(specText) as Record<string, unknown>;
    } catch {
      setError("策略 JSON 格式不正確。");
      return;
    }
    setIsRunning(true);
    try {
      const result = await runBacktest(parsed);
      setMessage(result.created ? "已建立新的回測結果。" : "相同設定已回測過，已載入既有結果。");
      setSelectedRun(result);
      await loadRuns();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "執行回測失敗。");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="麵包屑">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>回測</span>
        </nav>

        <PageHeader
          kicker="Capital"
          title="回測引擎 v0"
          description="用已匯入的日 K 與三大法人資料，跑決定論的 swing 策略回測與 70/30 walk-forward 檢查。"
          actions={<Link className="button" href="/capital/market-data">市場資料</Link>}
        />

        <section className="panel">
          <div className={styles.warningLine}>費率為預設值：期貨手續費暫用 TWD 50/口/邊；結果只供研究，不是交易建議。</div>
          <div className={styles.noteGrid}>
            <span>TX / MTX / TMF 點值：200 / 50 / 10</span>
            <span>期交稅率：0.00002</span>
            <span>US 滑價：成交金額 0.05%/邊，不做 TWD 換算</span>
            <span>停損停利以日收盤檢查，不看盤中高低</span>
          </div>
        </section>

        <section className={styles.layout}>
          <div className="form-panel">
            <h2>新增回測</h2>
            <label>
              <span>策略規格 JSON</span>
              <textarea className={styles.specBox} value={specText} onChange={(event) => setSpecText(event.target.value)} />
            </label>
            <div className={styles.toolbar}>
              <button className="button button-primary" type="button" disabled={isRunning} onClick={() => void submitRun()}>
                {isRunning ? "回測中..." : "執行回測"}
              </button>
              <button className="button" type="button" disabled={isLoading} onClick={() => void loadRuns()}>重新整理</button>
            </div>
            {message ? <div className="notice">{message}</div> : null}
            {error ? <div className="notice notice-error">{error}</div> : null}
          </div>

          <div className="panel">
            <h2>回測紀錄</h2>
            <RunList runs={runs} selectedRunId={selectedRun?.id ?? null} onSelect={setSelectedRun} />
          </div>
        </section>

        <ResultPanel run={selectedRun} />
      </div>
    </main>
  );
}

function RunList({ runs, selectedRunId, onSelect }: { runs: BacktestRun[]; selectedRunId: number | null; onSelect: (run: BacktestRun) => void }) {
  if (runs.length === 0) return <p className="pending-text">尚無回測紀錄</p>;
  return (
    <div className={styles.runList}>
      {runs.map((run) => (
        <button
          key={run.id}
          type="button"
          className={`${styles.runButton} ${selectedRunId === run.id ? styles.runButtonActive : ""}`}
          onClick={() => onSelect(run)}
        >
          <span>{String(run.spec_snapshot.name ?? `回測 ${run.id}`)}</span>
          <small>{run.range_start} 到 {run.range_end}</small>
        </button>
      ))}
    </div>
  );
}

function ResultPanel({ run }: { run: BacktestRun | null }) {
  const full = run?.results.full;
  const split = run?.results.split;
  const taxUrl = run?.results.tax_source_url;
  const limitations = useMemo(() => run?.results.known_limitations ?? [], [run]);

  if (!run || !full) {
    return (
      <section className="panel">
        <h2>回測結果</h2>
        <p className="pending-text">尚未選取回測結果</p>
      </section>
    );
  }

  return (
    <>
      <section className="panel">
        <div className="stage-header">
          <h2>回測結果</h2>
          <span className="stage-pill">run_hash 冪等：{run.run_hash.slice(0, 12)}</span>
        </div>
        <div className={styles.strategyMetrics}>
          <KpiCard label="淨利" value={`${full.metrics.net_pnl} ${full.trades[0]?.currency ?? ""}`} tone={Number(full.metrics.net_pnl) >= 0 ? "gain" : "loss"} note="扣除費用、稅與滑價" />
          <KpiCard label="勝率" value={`${(full.metrics.win_rate * 100).toFixed(1)}%`} tone="accent" note={`${full.metrics.trade_count} 筆交易`} />
          <KpiCard label="最大回撤" value={full.metrics.max_drawdown} tone="loss" note="完整樣本區間" />
          <KpiCard label="期望值" value={full.metrics.expectancy} tone={Number(full.metrics.expectancy) >= 0 ? "gain" : "loss"} note={`曝險 ${full.metrics.exposure_days} 天`} />
        </div>
        <div className={styles.resultTabs} role="tablist" aria-label="策略測試結果">
          <span className={styles.activeResultTab}>績效摘要</span>
          <span>交易分析</span>
          <span>樣本切分</span>
        </div>
        <div className={styles.metaBlock}>
          <p>{run.results.cost_disclaimer || "費率為預設值"}</p>
          {taxUrl ? <p>期交稅來源：<a href={taxUrl} target="_blank" rel="noreferrer">期貨交易稅條例</a></p> : null}
          {split ? <p>Walk-forward：IS {String(split.in_sample_start)} 到 {String(split.in_sample_end)}；OOS {String(split.out_sample_start)} 到 {String(split.out_sample_end)}；衰退比 {String(split.decay_ratio)}</p> : null}
          {limitations.length ? <p>限制：{limitations.join("、")}</p> : null}
        </div>
      </section>

      <section className="panel">
        <h2>逐筆交易</h2>
        <TradesTable trades={full.trades} />
      </section>

      <section className="panel">
        <h2>樣本切分</h2>
        <WindowTable label="樣本內" result={run.results.in_sample} />
        <WindowTable label="樣本外" result={run.results.out_of_sample} />
      </section>
    </>
  );
}

function TradesTable({ trades }: { trades: BacktestTrade[] }) {
  if (trades.length === 0) return <p className="pending-text">沒有產生交易</p>;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr><th>進場</th><th>出場</th><th>進場價</th><th>出場價</th><th>毛損益</th><th>費用</th><th>稅</th><th>滑價</th><th>淨損益</th></tr>
        </thead>
        <tbody>
          {trades.map((trade, index) => (
            <tr key={`${trade.entry_date}-${trade.exit_date}-${index}`}>
              <td>{trade.entry_date}</td>
              <td>{trade.exit_date}</td>
              <td>{trade.entry_price}</td>
              <td>{trade.exit_price}</td>
              <td>{trade.gross_pnl}</td>
              <td>{trade.fee}</td>
              <td>{trade.tax}</td>
              <td>{trade.slippage}</td>
              <td className={Number(trade.net_pnl) >= 0 ? styles.positive : styles.negative}>{trade.net_pnl} {trade.currency}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WindowTable({ label, result }: { label: string; result?: BacktestWindowResult }) {
  if (!result) return null;
  return (
    <div className={styles.windowRow}>
      <strong>{label}</strong>
      <span>交易 {result.metrics.trade_count}</span>
      <span>淨損益 {result.metrics.net_pnl}</span>
      <span>期望值 {result.metrics.expectancy}</span>
      <span>最大回撤 {result.metrics.max_drawdown}</span>
    </div>
  );
}
