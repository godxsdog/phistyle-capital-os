"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { PageHeader } from "../../../components/ui";
import {
  TradePlan,
  TradePlanCreateRequest,
  TradePlanStats,
  closeTradePlan,
  createTradePlan,
  getTradePlanStats,
  listTradePlans,
  markTradePlans,
} from "../../../lib/capitalApi";
import { DIRECTION_LABELS, MARKET_LABELS, RISK_LABELS, labelFor } from "../../../lib/displayConstants";
import styles from "./TradePlansPage.module.css";

const INITIAL_FORM: TradePlanCreateRequest = {
  market: "taifex",
  symbol: "TX",
  direction: "long",
  planned_entry: "",
  stop_price: "",
  target_price: "",
  quantity: "1",
  declared_capital_twd: "",
  thesis: "",
  strategy_spec_id: null,
  is_paper: true,
  created_by: "Kaichang",
};

export default function TradePlansPage() {
  const [plans, setPlans] = useState<TradePlan[]>([]);
  const [stats, setStats] = useState<TradePlanStats | null>(null);
  const [form, setForm] = useState<TradePlanCreateRequest>(INITIAL_FORM);
  const [closeInputs, setCloseInputs] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setIsLoading(true);
    try {
      const [nextPlans, nextStats] = await Promise.all([listTradePlans(), getTradePlanStats()]);
      setPlans(nextPlans);
      setStats(nextStats);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "讀取交易計畫失敗。");
    } finally {
      setIsLoading(false);
    }
  }

  async function submitPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const created = await createTradePlan({ ...form, target_price: form.target_price || null });
      setMessage(`已建立交易計畫 #${created.id}，決策風險層級：${labelRisk(created.decision_request_risk_level)}`);
      setForm(INITIAL_FORM);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "建立交易計畫失敗。");
    }
  }

  async function runMark() {
    try {
      const result = await markTradePlans();
      setMessage(`已更新盯市：新增 ${result.inserted}，略過 ${result.skipped}，警告 ${result.warnings.length}`);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "盯市更新失敗。");
    }
  }

  async function closePlan(plan: TradePlan) {
    const exitPrice = closeInputs[plan.id];
    if (!exitPrice) {
      setError("請先輸入出場價格。");
      return;
    }
    try {
      const outcome = await closeTradePlan(plan.id, exitPrice, "使用者手動結案");
      setMessage(`計畫 #${plan.id} 已結案，損益 ${outcome.gross_pnl} ${outcome.currency}`);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "結案失敗。");
    }
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="麵包屑">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>交易計畫</span>
        </nav>

        <PageHeader
          kicker="Capital"
          title="交易計畫"
          description="建立紙上交易計畫，先做風控檢查，再進既有決策審查流程；系統不會下單或自動平倉。"
          actions={<Link className="button" href="/capital/decisions">決策列表</Link>}
        />

        <form className="form-panel" onSubmit={submitPlan}>
          <h2>新增計畫</h2>
          <div className={styles.grid}>
            <label><span>市場</span><select value={form.market} onChange={(event) => setForm({ ...form, market: event.target.value as "taifex" | "us", symbol: event.target.value === "taifex" ? "TX" : "" })}><option value="taifex">台指期</option><option value="us">美股</option></select></label>
            <label><span>標的</span>{form.market === "taifex" ? <select value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value })}><option value="TX">TX</option><option value="MTX">MTX</option><option value="TMF">TMF</option></select> : <input value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value })} placeholder="AAPL" required />}</label>
            <label><span>方向</span><select value={form.direction} onChange={(event) => setForm({ ...form, direction: event.target.value as "long" | "short" })}><option value="long">做多</option><option value="short">做空</option></select></label>
            <label><span>數量</span><input value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} required /></label>
            <label><span>計畫進場</span><input value={form.planned_entry} onChange={(event) => setForm({ ...form, planned_entry: event.target.value })} required /></label>
            <label><span>停損</span><input value={form.stop_price} onChange={(event) => setForm({ ...form, stop_price: event.target.value })} required /></label>
            <label><span>目標價</span><input value={form.target_price || ""} onChange={(event) => setForm({ ...form, target_price: event.target.value })} /></label>
            <label><span>宣告資本 TWD</span><input value={form.declared_capital_twd} onChange={(event) => setForm({ ...form, declared_capital_twd: event.target.value })} required /></label>
          </div>
          <label><span>交易論點</span><textarea value={form.thesis} onChange={(event) => setForm({ ...form, thesis: event.target.value })} rows={4} required /></label>
          <label><span>建立者</span><input value={form.created_by} onChange={(event) => setForm({ ...form, created_by: event.target.value })} required /></label>
          <div className="form-actions"><button className="button button-primary" type="submit">建立並送審</button></div>
        </form>

        {message ? <div className="notice">{message}</div> : null}
        {error ? <div className="notice notice-error">{error}</div> : null}

        <section className="panel">
          <div className="stage-header">
            <h2>計畫列表</h2>
            <button className="button" type="button" onClick={() => void runMark()}>手動盯市</button>
          </div>
          {isLoading ? <p className="pending-text">載入中...</p> : <PlansTable plans={plans} closeInputs={closeInputs} setCloseInputs={setCloseInputs} closePlan={closePlan} />}
        </section>

        <section className="panel">
          <h2>分幣別統計</h2>
          <Stats stats={stats} />
        </section>
      </div>
    </main>
  );
}

function PlansTable({ plans, closeInputs, setCloseInputs, closePlan }: { plans: TradePlan[]; closeInputs: Record<number, string>; setCloseInputs: (value: Record<number, string>) => void; closePlan: (plan: TradePlan) => void }) {
  if (plans.length === 0) return <p className="pending-text">尚無交易計畫</p>;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead><tr><th>編號</th><th>標的</th><th>計畫</th><th>風控</th><th>決策</th><th>手動結案</th></tr></thead>
        <tbody>
          {plans.map((plan) => (
            <tr key={plan.id}>
              <td>#{plan.id}</td>
              <td>{labelFor(MARKET_LABELS, plan.market)} {plan.symbol}</td>
              <td>{labelFor(DIRECTION_LABELS, plan.direction)} / 進 {plan.planned_entry} / 停 {plan.stop_price} / 量 {plan.quantity}</td>
              <td className={plan.risk_check.passed ? styles.ok : styles.warn}>{plan.risk_check.passed ? "通過" : "需高風險審查"}<br />風險 {plan.risk_check.risk_amount} {plan.risk_check.risk_currency}</td>
              <td><Link className="button" href={`/capital/decisions/${plan.decision_request_id}`}>開啟審查</Link></td>
              <td><div className={styles.actions}><input value={closeInputs[plan.id] || ""} onChange={(event) => setCloseInputs({ ...closeInputs, [plan.id]: event.target.value })} placeholder="出場價" /><button className="button" type="button" onClick={() => closePlan(plan)}>結案</button></div></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Stats({ stats }: { stats: TradePlanStats | null }) {
  if (!stats || stats.by_currency.length === 0) return <p className="pending-text">尚無已結案計畫</p>;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead><tr><th>幣別</th><th>結案數</th><th>勝率</th><th>期望值</th><th>總損益</th><th>計畫遵守率</th></tr></thead>
        <tbody>
          {stats.by_currency.map((row) => (
            <tr key={row.currency}>
              <td>{row.currency}</td>
              <td>{row.closed_plan_count}</td>
              <td>{Math.round(row.win_rate * 100)}%</td>
              <td>{row.expectancy}</td>
              <td><span className={Number(row.gross_pnl) >= 0 ? "text-gain" : "text-loss"}>{row.gross_pnl}</span></td>
              <td>{Math.round(row.plan_adherence_rate * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function labelRisk(value: string): string {
  return labelFor(RISK_LABELS, value);
}
