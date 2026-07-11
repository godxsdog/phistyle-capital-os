"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  FxRate,
  Program,
  QuestResult,
  TripQuest,
  createAwardQuote,
  listFxRates,
  listPrograms,
  listQuestResults,
  listTripQuests,
  runTripQuest,
} from "../../../lib/walletApi";
import { PageHeader } from "../../../components/ui";
import styles from "./QuestPage.module.css";

const PREF_KEY = "phistyle.wallet.quest.preferences";

type QuestPrefs = {
  mode: "round_trip" | "chain";
  origin: string;
  destination: string;
  programNames: string[];
  tripDays: string;
  cabin: string;
  pax: string;
  segments: Array<{ origin: string; destination: string }>;
};

const DEFAULT_PREFS: QuestPrefs = {
  mode: "round_trip",
  origin: "TPE",
  destination: "OKA",
  programNames: [],
  tripDays: "4",
  cabin: "economy",
  pax: "2",
  segments: [{ origin: "TPE", destination: "SIN" }, { origin: "SIN", destination: "MLE" }],
};

export default function TripQuestPage() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [quests, setQuests] = useState<TripQuest[]>([]);
  const [fxRates, setFxRates] = useState<FxRate[]>([]);
  const [prefs, setPrefs] = useState<QuestPrefs>(DEFAULT_PREFS);
  const [activeQuest, setActiveQuest] = useState<TripQuest | null>(null);
  const [results, setResults] = useState<QuestResult[]>([]);
  const [promotedIds, setPromotedIds] = useState<number[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(PREF_KEY);
      if (stored) setPrefs({ ...DEFAULT_PREFS, ...(JSON.parse(stored) as Partial<QuestPrefs>) });
    } catch {
      window.localStorage.removeItem(PREF_KEY);
    }
    void loadPage();
  }, []);

  useEffect(() => {
    window.localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
  }, [prefs]);

  const airlinePrograms = useMemo(() => programs.filter((program) => program.kind === "airline"), [programs]);

  async function loadPage() {
    try {
      const [nextPrograms, nextQuests, nextRates] = await Promise.all([listPrograms(), listTripQuests(), listFxRates()]);
      setPrograms(nextPrograms);
      setQuests(nextQuests);
      setFxRates(nextRates);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "旅程尋票資料載入失敗。");
    }
  }

  async function submitQuest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setIsRunning(true);
    setMessage(null);
    setError(null);
    try {
      const response = await runTripQuest({
        origin: prefs.mode === "chain" ? prefs.segments[0].origin : prefs.origin,
        destination: prefs.mode === "chain" ? prefs.segments[prefs.segments.length - 1].destination : prefs.destination,
        programs: prefs.programNames,
        window_start: field(data, "window_start"),
        window_end: field(data, "window_end"),
        trip_days: Number(prefs.tripDays),
        cabin: prefs.cabin,
        pax: Number(prefs.pax),
        kind: prefs.mode,
        segments: prefs.mode === "chain" ? prefs.segments : undefined,
      });
      setActiveQuest(response.quest);
      setResults(response.results);
      setMessage(response.created_results > 0 ? `找到 ${response.results.length} 組來回組合。` : "已重用今日快照與結果，沒有重打 seats.aero。所選條件若無結果，請稍後或改日期窗再試。");
      await loadPage();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "旅程尋票失敗。");
    } finally {
      setIsRunning(false);
    }
  }

  async function openQuest(quest: TripQuest) {
    try {
      setActiveQuest(quest);
      const rows = await listQuestResults(quest.id);
      const latestRunDate = rows[0]?.run_date;
      setResults(latestRunDate ? rows.filter((row) => row.run_date === latestRunDate) : []);
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "讀取旅程結果失敗。");
    }
  }

  async function promote(result: QuestResult) {
    const quest = activeQuest || quests.find((item) => item.id === result.trip_quest_id);
    const program = programs.find((item) => slug(item.name) === slug(result.program));
    if (!quest || !program) {
      setError("找不到對應的旅程或點數計畫，無法升格。");
      return;
    }
    try {
      if (quest.kind === "chain") {
        const segments = parseSegments(result.segments_json);
        for (const [index, segment] of segments.entries()) {
          const tax = parseTax(segment.taxes);
          await createAwardQuote({
            origin: segment.origin,
            destination: segment.destination,
            travel_date: segment.date,
            cabin: quest.cabin,
            pax: quest.pax,
            program_id: program.id,
            miles_required: segment.miles_required,
            taxes_amount: tax?.amount || null,
            taxes_currency: tax?.currency || null,
            source: "trip_quest",
            note: `多段尋票 #${result.id} 第${index + 1}段`,
          });
        }
        setPromotedIds((current) => [...current, result.id]);
        setMessage(`已建立 ${segments.length} 筆分段票券需求，可前往 PW-2 分別比價。`);
        return;
      }
      const outboundTax = parseTax(result.outbound_taxes);
      const returnTax = parseTax(result.return_taxes);
      await createAwardQuote({
        origin: quest.origin,
        destination: quest.destination,
        travel_date: result.outbound_date,
        cabin: quest.cabin,
        pax: quest.pax,
        program_id: program.id,
        miles_required: result.outbound_miles,
        taxes_amount: outboundTax?.amount || null,
        taxes_currency: outboundTax?.currency || null,
        source: "trip_quest",
        note: `旅程尋票 #${result.id} 去程`,
      });
      await createAwardQuote({
        origin: quest.destination,
        destination: quest.origin,
        travel_date: result.return_date,
        cabin: quest.cabin,
        pax: quest.pax,
        program_id: program.id,
        miles_required: result.return_miles,
        taxes_amount: returnTax?.amount || null,
        taxes_currency: returnTax?.currency || null,
        source: "trip_quest",
        note: `旅程尋票 #${result.id} 回程`,
      });
      setPromotedIds((current) => [...current, result.id]);
      setMessage("已建立去程與回程兩筆票券需求，可前往 PW-2 分別比價。");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "升格票券需求失敗。");
    }
  }

  return (
    <main><div className="shell">
      <nav className="breadcrumb" aria-label="麵包屑"><Link href="/">PhiStyle OS</Link><span>/</span><Link href="/wallet">點數錢包</Link><span>/</span><span>旅程尋票</span></nav>
      <PageHeader kicker="Point Wallet" title="旅程尋票器" description="一次找出去程與回程，依總哩程與出發日排序；只查 cached search，不會訂票。" actions={<Link className="button" href="/wallet/awards">換票比價</Link>} />
      {error ? <div className="notice notice-error">{error}</div> : null}
      {message ? <div className="notice">{message}</div> : null}

      <form className={`${styles.questForm} panel`} onSubmit={submitQuest}>
        <div className={styles.modeSwitch} role="group" aria-label="尋票模式">
          <button className={`button ${prefs.mode === "round_trip" ? "button-primary" : ""}`} type="button" onClick={() => setPrefs({ ...prefs, mode: "round_trip" })}>來回</button>
          <button className={`button ${prefs.mode === "chain" ? "button-primary" : ""}`} type="button" onClick={() => setPrefs({ ...prefs, mode: "chain" })}>多段同日</button>
        </div>
        {prefs.mode === "round_trip" ? <div className={styles.routeInputs}>
          <label><span>出發地</span><input value={prefs.origin} maxLength={3} onChange={(event) => setPrefs({ ...prefs, origin: event.target.value.toUpperCase() })} required /></label>
          <span className={styles.routeArrow}>⇄</span>
          <label><span>目的地</span><input value={prefs.destination} maxLength={3} onChange={(event) => setPrefs({ ...prefs, destination: event.target.value.toUpperCase() })} required /></label>
        </div> : <div className={styles.segmentEditor}>
          {prefs.segments.map((segment, index) => <div className={styles.segmentRow} key={index}>
            <strong>第 {index + 1} 段</strong>
            <input aria-label={`第 ${index + 1} 段出發地`} value={segment.origin} maxLength={3} onChange={(event) => updateSegment(index, "origin", event.target.value.toUpperCase(), prefs, setPrefs)} required />
            <span>→</span>
            <input aria-label={`第 ${index + 1} 段目的地`} value={segment.destination} maxLength={3} onChange={(event) => updateSegment(index, "destination", event.target.value.toUpperCase(), prefs, setPrefs)} required />
            <button className="button" disabled={prefs.segments.length <= 2} type="button" onClick={() => setPrefs({ ...prefs, segments: prefs.segments.filter((_, itemIndex) => itemIndex !== index) })}>−</button>
          </div>)}
          <button className="button" disabled={prefs.segments.length >= 3} type="button" onClick={() => setPrefs({ ...prefs, segments: [...prefs.segments, { origin: prefs.segments[prefs.segments.length - 1].destination, destination: "" }] })}>＋新增航段</button>
          <p className="subtle">同日即視為可接；實際轉機時間與機場請自行確認。</p>
        </div>}
        <div className={styles.dateRow}>
          <label><span>開始日期</span><input name="window_start" type="date" required /></label>
          <label><span>結束日期</span><input name="window_end" type="date" required /></label>
        </div>
        <fieldset className={styles.programPicker}>
          <legend>點數計畫（可多選）</legend>
          {airlinePrograms.map((program) => (
            <label key={program.id}><input type="checkbox" checked={prefs.programNames.includes(program.name)} onChange={(event) => setPrefs({ ...prefs, programNames: event.target.checked ? [...prefs.programNames, program.name] : prefs.programNames.filter((name) => name !== program.name) })} />{program.name}</label>
          ))}
        </fieldset>
        <div className={styles.optionRow}>
          {prefs.mode === "round_trip" ? <label><span>旅程天數</span><input value={prefs.tripDays} onChange={(event) => setPrefs({ ...prefs, tripDays: event.target.value })} inputMode="numeric" required /></label> : null}
          <label><span>艙等</span><select value={prefs.cabin} onChange={(event) => setPrefs({ ...prefs, cabin: event.target.value })}><option value="economy">經濟艙</option><option value="premium">豪華經濟艙</option><option value="business">商務艙</option><option value="first">頭等艙</option></select></label>
          <label><span>人數</span><input value={prefs.pax} onChange={(event) => setPrefs({ ...prefs, pax: event.target.value })} inputMode="numeric" required /></label>
          <button className="button button-primary" disabled={isRunning || prefs.programNames.length === 0} type="submit">{isRunning ? "尋找中..." : "開始尋票"}</button>
        </div>
        <p className="subtle">{prefs.mode === "round_trip" ? "回程容忍旅程天數 ±1 天；" : "所有航段必須同日且同一點數計畫；"}同一查詢當日重跑會使用既有快照，節省 Pro 額度。</p>
      </form>

      <section className="panel">
        <div className="stage-header"><div><h2>尋票結果</h2>{activeQuest ? <p className="subtle">{questRouteLabel(activeQuest)} · {activeQuest.window_start}～{activeQuest.window_end}</p> : null}</div><span className="stage-pill">總哩程優先</span></div>
        {results.length === 0 ? <p className="pending-text">尚無配對結果。輸入條件後開始尋票。</p> : <div className={styles.resultList}>{results.map((result) => <ResultCard key={result.id} result={result} quest={activeQuest} fxRates={fxRates} promoted={promotedIds.includes(result.id)} onPromote={() => void promote(result)} />)}</div>}
      </section>

      <section className="panel"><h2>過往查詢</h2><div className={styles.questHistory}>{quests.map((quest) => <button className="button" key={quest.id} type="button" onClick={() => void openQuest(quest)}>#{quest.id} {questRouteLabel(quest)} · {quest.window_start}～{quest.window_end}</button>)}{quests.length === 0 ? <p className="pending-text">尚無查詢紀錄。</p> : null}</div></section>
    </div></main>
  );
}

function ResultCard({ result, quest, fxRates, promoted, onPromote }: { result: QuestResult; quest: TripQuest | null; fxRates: FxRate[]; promoted: boolean; onPromote: () => void }) {
  const verified = isBucketVerified(result.raw_refs);
  const segments = parseSegments(result.segments_json);
  return <article className={`${styles.resultCard} ${result.rank === 1 ? styles.winner : ""}`}>
    {result.rank === 1 ? <div className={styles.winnerBand}>♛ 第一名</div> : null}
    {quest?.kind === "chain" ? <div className={styles.resultDate}>{formatQuestDate(segments[0]?.date ?? result.outbound_date)}</div> : null}
    <div className={styles.resultRank}>#{result.rank}</div>
    {quest?.kind === "chain" ? <div className={styles.chainLegs}>{segments.map((segment, index) => <div className={styles.leg} key={`${segment.origin}-${segment.destination}-${index}`}><span>第 {index + 1} 段 {segment.origin} → {segment.destination}</span><strong>{formatPoints(segment.miles_required)} 哩</strong><small>{taxDisplay(segment.taxes, fxRates)}</small></div>)}</div> : <>
      <div className={styles.leg}><span>去程 {result.outbound_date.replaceAll("-", "/")}</span><strong>{formatPoints(result.outbound_miles)} 哩</strong><small>{taxDisplay(result.outbound_taxes, fxRates)}</small></div>
      <div className={styles.leg}><span>回程 {result.return_date.replaceAll("-", "/")}</span><strong>{formatPoints(result.return_miles)} 哩</strong><small>{taxDisplay(result.return_taxes, fxRates)}</small></div>
    </>}
    <div className={styles.total}><span>{result.program}</span><strong>{formatPoints(result.total_miles)} 哩</strong><small>剩餘座位至少 {result.seats_min} 席</small><em className={verified ? styles.verifiedBadge : styles.unverifiedBadge}>{verified ? "已驗證桶價" : "⚠️未驗證桶價，訂前請核官網"}</em></div>
    <button className="button button-primary" disabled={promoted} onClick={onPromote} type="button">{promoted ? "已升格" : "升格為票券需求"}</button>
  </article>;
}

function parseTax(value: string | null): { amount: string; currency: string } | null {
  if (!value) return null;
  const match = value.trim().match(/^([0-9]+(?:\.[0-9]+)?)\s+([A-Za-z]{3})$/);
  return match ? { amount: match[1], currency: match[2].toUpperCase() } : null;
}

function taxDisplay(value: string | null, rates: FxRate[]): string {
  if (!value) return "稅金未提供";
  const parsed = parseTax(value);
  if (!parsed) return `稅金 ${value}`;
  const rate = rates.find((item) => item.currency === parsed.currency);
  const twd = rate ? Number(parsed.amount) * Number(rate.twd_per_unit) : null;
  return `稅金 ${parsed.amount} ${parsed.currency}${twd === null ? "" : `（≈NT$${Math.round(twd).toLocaleString("zh-TW")}）`}`;
}

function formatPoints(value: string): string { return Number(value).toLocaleString("zh-TW", { maximumFractionDigits: 0 }); }
function formatQuestDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return value.replaceAll("-", "/");
  const weekday = new Intl.DateTimeFormat("zh-TW", { weekday: "short", timeZone: "UTC" }).format(new Date(Date.UTC(year, month - 1, day)));
  return `${year}/${String(month).padStart(2, "0")}/${String(day).padStart(2, "0")}（${weekday}）`;
}
function slug(value: string): string { return value.toLowerCase().replace(/[\s_-]/g, ""); }
function field(data: FormData, name: string): string { const value = data.get(name); return typeof value === "string" ? value : ""; }
function isBucketVerified(value: string | null): boolean { try { return Boolean(value && (JSON.parse(value) as { bucket_verified?: boolean }).bucket_verified); } catch { return false; } }
type ResultSegment = { origin: string; destination: string; date: string; miles_required: string; remaining_seats: number; taxes: string | null };
function parseSegments(value: string | null): ResultSegment[] { try { const rows = value ? JSON.parse(value) : []; return Array.isArray(rows) ? rows as ResultSegment[] : []; } catch { return []; } }
function questRouteLabel(quest: TripQuest): string { return quest.kind === "chain" && quest.segments ? quest.segments.map((segment) => segment.origin).concat(quest.segments[quest.segments.length - 1].destination).join(" → ") : `${quest.origin} ⇄ ${quest.destination}`; }
function updateSegment(index: number, key: "origin" | "destination", value: string, prefs: QuestPrefs, setPrefs: (value: QuestPrefs) => void) { setPrefs({ ...prefs, segments: prefs.segments.map((segment, itemIndex) => itemIndex === index ? { ...segment, [key]: value } : segment) }); }
