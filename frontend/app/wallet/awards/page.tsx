"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  AwardQuote,
  FundingScenario,
  Program,
  createAwardQuote,
  evaluateAwardQuote,
  listAwardQuotes,
  listFundingScenarios,
  listPrograms,
} from "../../../lib/walletApi";
import { CURRENCY_OPTIONS, OWNER_LABELS } from "../constants";
import styles from "../WalletPage.module.css";

const PREF_KEY = "phistyle.wallet.award.preferences";

type AwardPrefs = {
  programId: string;
  currency: string;
  cabin: string;
};

const DEFAULT_PREFS: AwardPrefs = {
  programId: "",
  currency: "TWD",
  cabin: "商務艙",
};

export default function WalletAwardsPage() {
  const [prefs, setPrefs] = useState<AwardPrefs>(DEFAULT_PREFS);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [quotes, setQuotes] = useState<AwardQuote[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState("");
  const [scenarios, setScenarios] = useState<FundingScenario[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(PREF_KEY);
    if (!stored) return;
    try {
      setPrefs({ ...DEFAULT_PREFS, ...(JSON.parse(stored) as Partial<AwardPrefs>) });
    } catch {
      window.localStorage.removeItem(PREF_KEY);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
  }, [prefs]);

  useEffect(() => {
    void loadPage();
  }, []);

  const selectedQuote = useMemo(
    () => quotes.find((quote) => String(quote.id) === selectedQuoteId) || quotes[0],
    [quotes, selectedQuoteId],
  );

  async function loadPage() {
    try {
      const [nextPrograms, nextQuotes] = await Promise.all([listPrograms(), listAwardQuotes()]);
      setPrograms(nextPrograms);
      setQuotes(nextQuotes);
      const nextSelected = selectedQuoteId || String(nextQuotes[0]?.id || "");
      setSelectedQuoteId(nextSelected);
      if (nextSelected) {
        setScenarios(await listFundingScenarios(Number(nextSelected)));
      }
      setError(null);
    } catch {
      setError("資料載入失敗，請稍後再試。");
    }
  }

  async function submitQuote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const quote = await createAwardQuote({
        origin: field(data, "origin"),
        destination: field(data, "destination"),
        travel_date: field(data, "travel_date"),
        cabin: field(data, "cabin"),
        pax: Number(field(data, "pax") || "1"),
        program_id: Number(field(data, "program_id")),
        miles_required: field(data, "miles_required"),
        taxes_amount: field(data, "taxes_amount") || null,
        taxes_currency: field(data, "taxes_currency") || null,
        cash_price_twd: field(data, "cash_price_twd") || null,
        source: "manual",
      });
      setStatus("票券需求已新增。");
      setSelectedQuoteId(String(quote.id));
      setScenarios([]);
      form.reset();
      await loadPage();
    } catch {
      setError("新增票券需求失敗，請確認欄位後再試。");
    }
  }

  async function evaluateSelected() {
    if (!selectedQuote) return;
    try {
      const rows = await evaluateAwardQuote(selectedQuote.id, today());
      setScenarios(rows);
      setExpanded(rows[0]?.id ?? null);
      setStatus("成本情境已重新評估；這不會消耗或修改任何點數。");
    } catch {
      setError("評估失敗，請確認資料完整後再試。");
    }
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="麵包屑">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <Link href="/wallet">點數錢包</Link>
          <span>/</span>
          <span>兌換成本</span>
        </nav>

        <section className="page-header">
          <div>
            <div className="section-kicker">兌換成本引擎</div>
            <h1>機票兌換成本比較</h1>
            <p>輸入一張想換的票，系統會比較既有點數、轉點、現買現轉、買分與現金票的真實新台幣成本。</p>
          </div>
          <Link className="button" href="/wallet">
            回點數錢包
          </Link>
        </section>

        {error ? <div className="notice notice-error">{error}</div> : null}
        {status ? <p className="subtle">{status}</p> : null}

        <div className={styles.grid}>
          <form className="form-panel" onSubmit={submitQuote}>
            <h2>新增票券需求</h2>
            <p className="subtle">在這裡輸入目的地、所需哩程、稅金與現金票價，系統只會建立一筆可重複評估的需求。</p>
            <div className={styles.formGrid}>
              <select name="program_id" value={prefs.programId} onChange={(event) => setPrefs({ ...prefs, programId: event.target.value })} required>
                <option value="">選擇兌換計畫</option>
                {programs.map((program) => (
                  <option key={program.id} value={program.id}>{program.name}</option>
                ))}
              </select>
              <input name="origin" placeholder="出發地，例如 TPE" />
              <input name="destination" placeholder="目的地，例如 TYO" />
              <input name="travel_date" type="date" defaultValue={today()} />
              <input name="cabin" value={prefs.cabin} onChange={(event) => setPrefs({ ...prefs, cabin: event.target.value })} placeholder="艙等" />
              <input name="pax" type="number" min="1" defaultValue="1" />
              <input name="miles_required" placeholder="所需哩程" required />
              <input name="taxes_amount" placeholder="稅金金額，可留空" />
              <select name="taxes_currency" value={prefs.currency} onChange={(event) => setPrefs({ ...prefs, currency: event.target.value })}>
                {CURRENCY_OPTIONS.map((currency) => (
                  <option key={currency} value={currency}>{currency}</option>
                ))}
              </select>
              <input name="cash_price_twd" placeholder="現金票價，TWD" />
              <button className="button button-primary" type="submit">
                新增需求
              </button>
            </div>
          </form>

          <section className="panel">
            <h2>選擇需求</h2>
            <p className="subtle">選一張票券需求後按下評估；每次評估會留下新的情境快照，點數帳本不會被修改。</p>
            <div className={styles.formGrid}>
              <select
                value={selectedQuote ? String(selectedQuote.id) : ""}
                onChange={async (event) => {
                  setSelectedQuoteId(event.target.value);
                  setScenarios(event.target.value ? await listFundingScenarios(Number(event.target.value)) : []);
                }}
              >
                {quotes.length === 0 ? <option value="">目前沒有票券需求</option> : null}
                {quotes.map((quote) => (
                  <option key={quote.id} value={quote.id}>
                    {quoteLabel(quote, programs)}
                  </option>
                ))}
              </select>
              <button className="button button-primary" type="button" onClick={evaluateSelected} disabled={!selectedQuote}>
                評估成本
              </button>
            </div>
          </section>
        </div>

        <section className="panel">
          <h2>成本情境排名</h2>
          <p className="subtle">排名依完成這張票的總成本排序，剩餘點數只供參考，不參與排名。</p>
          {scenarios.length === 0 ? (
            <p className="pending-text">目前沒有評估結果。</p>
          ) : (
            <div className={styles.ruleList}>
              {scenarios.map((scenario) => (
                <article className={styles.ruleSentence} key={scenario.id}>
                  <button className="button" type="button" onClick={() => setExpanded(expanded === scenario.id ? null : scenario.id)}>
                    #{scenario.rank} {methodLabel(scenario.method)} · {ownerLabel(scenario.owner)} · {formatMoney(scenario.total_cash_cost_twd)}
                  </button>
                  <p>
                    每點成本 {costPerPoint(scenario.effective_cpp)}，
                    取得 {formatNumber(scenario.points_acquired)} 點，
                    消耗 {formatNumber(scenario.points_consumed)} 點，
                    剩餘 {formatNumber(scenario.points_leftover)} 點
                    {scenario.saving_vs_cash_twd ? `，相對現金票省 ${formatMoney(scenario.saving_vs_cash_twd)}` : ""}
                  </p>
                  {scenario.warnings ? <p className="subtle">提醒：{scenario.warnings}</p> : null}
                  {expanded === scenario.id ? (
                    <div className={styles.formGrid}>
                      {pathDetails(scenario.path_json).map((line) => (
                        <p className="subtle" key={line}>{line}</p>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function field(data: FormData, name: string): string {
  const value = data.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function quoteLabel(quote: AwardQuote, programs: Program[]): string {
  const program = programs.find((item) => item.id === quote.program_id)?.name || "未命名計畫";
  const route = [quote.origin, quote.destination].filter(Boolean).join(" → ") || "未填航線";
  return `${program} · ${route} · ${formatNumber(quote.miles_required)} 點`;
}

function ownerLabel(owner: string): string {
  return OWNER_LABELS[owner] || "現金";
}

function methodLabel(method: string): string {
  const labels: Record<string, string> = {
    existing: "既有點數",
    transfer_chain: "轉點路徑",
    purchase_official: "官方買分",
    purchase_third_party: "第三方買分",
    cash: "現金票",
  };
  return labels[method] || method;
}

function pathDetails(raw: string): string[] {
  try {
    const path = JSON.parse(raw) as Record<string, unknown>;
    const lines: string[] = [];
    if (path.funding === "existing_points") lines.push("資金來源：既有點數");
    if (path.funding === "same_day_source_purchase") lines.push(`資金來源：當日購入來源點數，買分價格 #${path.purchase_offer_id}`);
    if (path.purchase_offer_id && !path.funding) lines.push(`買分價格 #${path.purchase_offer_id}`);
    if (path.cash_price_twd) lines.push(`現金票價：${formatMoney(String(path.cash_price_twd))}`);
    const hops = Array.isArray(path.hops) ? path.hops : [];
    for (const hop of hops) {
      const item = hop as Record<string, unknown>;
      lines.push(`${item.from_program_name} → ${item.to_program_name}：送出 ${formatNumber(String(item.sent))} 點，取得 ${formatNumber(String(item.received))} 點（規則 #${item.rule_id}）`);
    }
    const lots = Array.isArray(path.lots_consumed) ? path.lots_consumed : [];
    for (const lot of lots) {
      const item = lot as Record<string, unknown>;
      lines.push(`成本批次 #${item.lot_id}：消耗 ${formatNumber(String(item.qty))} 點，成本 ${formatMoney(String(item.cost_twd))}`);
    }
    return lines.length > 0 ? lines : ["此情境沒有額外路徑細節。"];
  } catch {
    return ["路徑細節暫時無法顯示。"];
  }
}

function formatMoney(value: string | number | null): string {
  const numberValue = Number(value || 0);
  return `NT$${numberValue.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}`;
}

function costPerPoint(value: string | number | null): string {
  if (value === null || value === undefined || value === "") return "未設定";
  return `NT$${Number(value).toLocaleString("zh-TW", { minimumFractionDigits: 3, maximumFractionDigits: 3 })}/點`;
}

function formatNumber(value: string | number | null): string {
  return Number(value || 0).toLocaleString("zh-TW", { maximumFractionDigits: 2 });
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}
