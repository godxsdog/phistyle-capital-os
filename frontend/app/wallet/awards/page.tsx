"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AwardQuote,
  AwardSnapshot,
  AwardWatch,
  FundingScenario,
  Program,
  createAwardQuote,
  createAwardWatch,
  evaluateAwardQuote,
  fetchAwardWatch,
  listAwardQuotes,
  listAwardSnapshots,
  listAwardWatches,
  listFundingScenarios,
  listPrograms,
  promoteAwardSnapshot,
} from "../../../lib/walletApi";
import { CURRENCY_OPTIONS, OWNER_LABELS } from "../constants";
import styles from "../WalletPage.module.css";
import {
  FAVORITE_PROGRAM_PREF_KEY,
  defaultFavoriteProgramIds,
  programDisplayName,
  sortPrograms,
} from "../programPreferences";

const PREF_KEY = "phistyle.wallet.award.preferences";

type AwardPrefs = {
  programId: string;
  currency: string;
};

const DEFAULT_PREFS: AwardPrefs = {
  programId: "",
  currency: "TWD",
};

export default function WalletAwardsPage() {
  const [prefs, setPrefs] = useState<AwardPrefs>(DEFAULT_PREFS);
  const [favoriteProgramIds, setFavoriteProgramIds] = useState<number[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [quotes, setQuotes] = useState<AwardQuote[]>([]);
  const [watches, setWatches] = useState<AwardWatch[]>([]);
  const [snapshots, setSnapshots] = useState<AwardSnapshot[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState("");
  const [scenarios, setScenarios] = useState<FundingScenario[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(PREF_KEY);
    const storedFavorites = window.localStorage.getItem(FAVORITE_PROGRAM_PREF_KEY);
    if (storedFavorites) setFavoriteProgramIds(JSON.parse(storedFavorites) as number[]);
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
  const sortedPrograms = useMemo(() => sortPrograms(programs, favoriteProgramIds), [favoriteProgramIds, programs]);
  const winner = scenarios[0] || null;

  async function loadPage() {
    try {
      const [nextPrograms, nextQuotes, nextWatches, nextSnapshots] = await Promise.all([
        listPrograms(),
        listAwardQuotes(),
        listAwardWatches(),
        listAwardSnapshots(),
      ]);
      const storedFavorites = window.localStorage.getItem(FAVORITE_PROGRAM_PREF_KEY);
      const nextFavorites = storedFavorites ? JSON.parse(storedFavorites) as number[] : defaultFavoriteProgramIds(nextPrograms);
      if (!storedFavorites) window.localStorage.setItem(FAVORITE_PROGRAM_PREF_KEY, JSON.stringify(nextFavorites));
      setFavoriteProgramIds(nextFavorites);
      setPrograms(nextPrograms);
      setQuotes(nextQuotes);
      setWatches(nextWatches);
      setSnapshots(nextSnapshots);
      if (!prefs.programId && nextFavorites.length > 0) {
        setPrefs((current) => ({ ...current, programId: String(nextFavorites[0]) }));
      }
      const nextSelected = selectedQuoteId || String(nextQuotes[0]?.id || "");
      setSelectedQuoteId(nextSelected);
      if (nextSelected) setScenarios(await listFundingScenarios(Number(nextSelected)));
      setError(null);
    } catch {
      setError("資料載入失敗，請稍後再試。");
    }
  }

  async function submitAndEvaluate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      const quote = await createAwardQuote({
        program_id: Number(field(data, "program_id")),
        miles_required: field(data, "miles_required"),
        taxes_amount: field(data, "taxes_amount") || null,
        taxes_currency: field(data, "taxes_currency") || null,
        cash_price_twd: field(data, "cash_price_twd") || null,
        pax: 1,
        source: "manual",
      });
      const rows = await evaluateAwardQuote(quote.id, today());
      setSelectedQuoteId(String(quote.id));
      setScenarios(rows);
      setExpanded(rows[0]?.id ?? null);
      setStatus("已完成比價；這不會消耗或修改任何點數。");
      form.reset();
      await loadPage();
      setScenarios(rows);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "比價失敗，請確認資料完整後再試。");
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

  async function createWatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await createAwardWatch({
        origin: field(data, "origin"),
        destination: field(data, "destination"),
        cabin: field(data, "cabin"),
        start_date: field(data, "start_date") || null,
        end_date: field(data, "end_date") || null,
        program_id: field(data, "program_id") ? Number(field(data, "program_id")) : null,
        active: true,
      });
      setStatus("已建立 seats.aero 監視路線。");
      form.reset();
      await loadPage();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "建立監視路線失敗。");
    }
  }

  async function fetchWatch(watchId: number) {
    try {
      await fetchAwardWatch(watchId, today());
      setStatus("已抓取 seats.aero 快照；同一天重跑不會重複建立。");
      await loadPage();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "抓取 seats.aero 失敗，請確認 API key 與路線。");
    }
  }

  async function promoteSnapshot(snapshotId: number) {
    try {
      const promoted = await promoteAwardSnapshot(snapshotId, 0);
      setSelectedQuoteId(String(promoted.award_quote.id));
      setScenarios([]);
      setStatus("已升格為票券需求；請補上現金票價後重新評估。");
      await loadPage();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "升格票券需求失敗。");
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
          <span>換票比價</span>
        </nav>

        <section className="page-header">
          <div>
            <div className="section-kicker">換票比價</div>
            <h1>我要換一張票，幫我算怎麼最划算</h1>
            <p>輸入哩程、稅金與現金票價，系統比較既有點數、轉點、買分與現金票。</p>
          </div>
          <Link className="button" href="/wallet">
            回點數錢包
          </Link>
        </section>

        {error ? <div className="notice notice-error">{error}</div> : null}
        {status ? <p className="subtle">{status}</p> : null}

        <form className={`${styles.stickySearch} panel`} onSubmit={submitAndEvaluate}>
          <div className={styles.searchHeading}>
            <div><div className="section-kicker">票券需求</div><h2>快速比價</h2></div>
            <span className="stage-pill">唯讀試算</span>
          </div>
          <div className={styles.awardLine}>
            <span>我要</span>
            <select name="program_id" value={prefs.programId} onChange={(event) => setPrefs({ ...prefs, programId: event.target.value })} required>
              <option value="">計畫</option>
              {sortedPrograms.map((program) => <option key={program.id} value={program.id}>{programDisplayName(program, favoriteProgramIds)}</option>)}
            </select>
            <input name="miles_required" placeholder="哩數" inputMode="numeric" required />
            <span>哩，稅金</span>
            <input name="taxes_amount" placeholder="金額" inputMode="decimal" />
            <select name="taxes_currency" value={prefs.currency} onChange={(event) => setPrefs({ ...prefs, currency: event.target.value })}>
              {CURRENCY_OPTIONS.map((currency) => <option key={currency} value={currency}>{currency}</option>)}
            </select>
            <span>現金票價</span>
            <input name="cash_price_twd" placeholder="NT$ 選填" inputMode="decimal" />
            <button className="button button-primary" type="submit">幫我比價</button>
          </div>
        </form>

        <section className="panel">
          <div className={styles.sectionHeader}>
            <div>
              <h2>seats.aero 監視</h2>
              <p className="subtle">使用 Partner API 的 Cached Search；不爬蟲、不訂票，只保存每日快照。</p>
            </div>
          </div>
          <form className={styles.awardLine} onSubmit={createWatch}>
            <input name="origin" placeholder="出發 TPE" maxLength={3} required />
            <input name="destination" placeholder="抵達 TYO" maxLength={3} required />
            <select name="cabin" defaultValue="business">
              <option value="economy">經濟艙</option>
              <option value="premium">豪華經濟艙</option>
              <option value="business">商務艙</option>
              <option value="first">頭等艙</option>
            </select>
            <input name="start_date" type="date" aria-label="開始日期" />
            <input name="end_date" type="date" aria-label="結束日期" />
            <select name="program_id" defaultValue="">
              <option value="">任何計畫</option>
              {sortedPrograms.map((program) => <option key={program.id} value={program.id}>{programDisplayName(program, favoriteProgramIds)}</option>)}
            </select>
            <button className="button button-primary" type="submit">新增監視</button>
          </form>

          <div className={styles.watchList}>
            {watches.length === 0 ? <p className="pending-text">目前沒有監視路線。</p> : null}
            {watches.map((watch) => (
              <article className={styles.watchItem} key={watch.id}>
                <strong>{watch.origin} → {watch.destination}</strong>
                <span>{cabinLabel(watch.cabin)} · {watch.start_date || "未指定"} ~ {watch.end_date || "未指定"}</span>
                <button className="button" type="button" onClick={() => fetchWatch(watch.id)}>抓取快照</button>
              </article>
            ))}
          </div>

          <h3>快照</h3>
          <div className={styles.watchList}>
            {snapshots.length === 0 ? <p className="pending-text">目前沒有快照。</p> : null}
            {snapshots.map((snapshot) => (
              <article className={styles.watchItem} key={snapshot.id}>
                <strong>{snapshot.seen_date}</strong>
                <span>{snapshot.result_count} 筆可用結果 · {snapshotPreview(snapshot)}</span>
                <button className="button" type="button" onClick={() => promoteSnapshot(snapshot.id)} disabled={snapshot.result_count === 0}>
                  升格為票券需求
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className={styles.sectionHeader}>
            <div>
              <h2>既有需求</h2>
              <p className="subtle">也可以重跑之前建立過的需求。</p>
            </div>
            <button className="button" type="button" onClick={evaluateSelected} disabled={!selectedQuote}>重新評估</button>
          </div>
          <select
            value={selectedQuote ? String(selectedQuote.id) : ""}
            onChange={async (event) => {
              setSelectedQuoteId(event.target.value);
              setScenarios(event.target.value ? await listFundingScenarios(Number(event.target.value)) : []);
            }}
          >
            {quotes.length === 0 ? <option value="">目前沒有票券需求</option> : null}
            {quotes.map((quote) => <option key={quote.id} value={quote.id}>{quoteLabel(quote, programs, favoriteProgramIds)}</option>)}
          </select>
          {selectedQuote?.note ? <small className="subtle">{selectedQuote.note}</small> : null}
        </section>

        <section className="panel">
          <div className={styles.sectionHeader}>
            <div>
              <h2>成本情境排名</h2>
              <p className="subtle">由總現金成本排序；點一下方案即可查看轉點與成本批次明細。</p>
            </div>
            {selectedQuote ? <strong>{quoteRouteSummary(selectedQuote, programs)}</strong> : null}
          </div>
          {scenarios.length === 0 ? (
            <p className="pending-text">目前沒有評估結果。</p>
          ) : (
            <div className={styles.flightResults}>
              {scenarios.map((scenario) => (
                <article
                  className={`${styles.flightResultCard} ${scenario.rank === 1 ? styles.bestFlightResult : ""}`}
                  key={scenario.id}
                  onClick={() => setExpanded(expanded === scenario.id ? null : scenario.id)}
                >
                  {scenario.rank === 1 ? <div className={styles.bestValueRibbon}>最划算</div> : null}
                  <div className={styles.flightOptionMain}>
                    <div className={styles.flightOptionIdentity}>
                      <span className={styles.rankBadge}>#{scenario.rank}</span>
                      <div>
                        <h3>{humanScenario(scenario)}</h3>
                        <p>{scenarioPathSummary(scenario)} · 剩餘 {formatNumber(scenario.points_leftover)} 點</p>
                      </div>
                    </div>
                    <div className={styles.flightOptionPrice}>
                      <strong>{formatMoney(scenario.total_cash_cost_twd)}</strong>
                      <small>{costPerPoint(scenario.effective_cpp)}</small>
                      {scenario.saving_vs_cash_twd ? <span>省下 {formatMoney(scenario.saving_vs_cash_twd)}</span> : null}
                    </div>
                  </div>
                  {expanded === scenario.id ? (
                    <div className={styles.awardDetail}>
                      {pathDetails(scenario.path_json).map((line) => <p className="subtle" key={line}>{line}</p>)}
                      {scenario.warnings ? <p className="subtle">提醒：{scenario.warnings}</p> : null}
                    </div>
                  ) : null}
                  <button className={styles.expandResult} type="button">
                    {expanded === scenario.id ? "收合明細" : "查看明細"}
                  </button>
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

function quoteLabel(quote: AwardQuote, programs: Program[], favoriteProgramIds: number[]): string {
  const program = programs.find((item) => item.id === quote.program_id);
  const programName = program ? programDisplayName(program, favoriteProgramIds) : "未命名計畫";
  return `${programName} · ${formatNumber(quote.miles_required)} 哩 · 稅金 ${quote.taxes_amount || 0} ${quote.taxes_currency || "TWD"}`;
}

function quoteRouteSummary(quote: AwardQuote, programs: Program[]): string {
  const program = programs.find((item) => item.id === quote.program_id);
  const route = quote.origin && quote.destination ? `${quote.origin} → ${quote.destination}` : program?.name || "票券需求";
  return `${route} · ${formatNumber(quote.miles_required)} 哩`;
}

function scenarioPathSummary(scenario: FundingScenario): string {
  try {
    const path = JSON.parse(scenario.path_json) as Record<string, unknown>;
    const hops = Array.isArray(path.hops) ? path.hops : [];
    if (hops.length > 0) {
      const names = hops.map((hop) => String((hop as Record<string, unknown>).to_program_name || "")).filter(Boolean);
      return `轉點路徑 ${names.join(" → ")}`;
    }
    if (path.funding === "existing_points") return "使用現有點數";
    if (path.funding === "same_day_source_purchase") return "當日買分後轉點";
    return "直接完成兌換";
  } catch {
    return "成本路徑";
  }
}

function humanScenario(scenario: FundingScenario): string {
  const owner = OWNER_LABELS[scenario.owner] || "現金";
  const labels: Record<string, string> = {
    existing: `用${owner}既有點數`,
    transfer_chain: `用${owner}既有來源點數轉換`,
    purchase_official: "官方買分後兌換",
    purchase_third_party: "第三方手動買分後兌換",
    cash: "直接買現金票",
  };
  return labels[scenario.method] || scenario.method;
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

function cabinLabel(value: string): string {
  const labels: Record<string, string> = {
    economy: "經濟艙",
    premium: "豪華經濟艙",
    business: "商務艙",
    first: "頭等艙",
  };
  return labels[value] || value;
}

function snapshotPreview(snapshot: AwardSnapshot): string {
  try {
    const rows = JSON.parse(snapshot.normalized_json) as Array<Record<string, unknown>>;
    const first = rows[0];
    if (!first) return "沒有可升格的結果";
    return `${first.origin || ""}→${first.destination || ""} ${first.travel_date || ""} ${formatNumber(String(first.miles_required || 0))} 哩`;
  } catch {
    return "快照資料暫時無法顯示";
  }
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}
