"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  HotelStayEvaluation,
  HotelStayOption,
  HotelStayQuote,
  Program,
  createHotelStayQuote,
  evaluateHotelStayQuote,
  listHotelStayQuotes,
  listPrograms,
} from "../../../lib/walletApi";
import { OWNER_LABELS } from "../constants";
import styles from "../WalletPage.module.css";
import {
  FAVORITE_PROGRAM_PREF_KEY,
  defaultFavoriteProgramIds,
  programDisplayName,
  sortPrograms,
} from "../programPreferences";

const PREF_KEY = "phistyle.wallet.hotel.preferences";

type HotelPrefs = {
  owner: "kent" | "wife";
  programId: string;
};

const DEFAULT_PREFS: HotelPrefs = {
  owner: "kent",
  programId: "",
};

export default function WalletHotelsPage() {
  const [prefs, setPrefs] = useState<HotelPrefs>(DEFAULT_PREFS);
  const [favoriteProgramIds, setFavoriteProgramIds] = useState<number[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [quotes, setQuotes] = useState<HotelStayQuote[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState("");
  const [evaluation, setEvaluation] = useState<HotelStayEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(PREF_KEY);
    const storedFavorites = window.localStorage.getItem(FAVORITE_PROGRAM_PREF_KEY);
    if (storedFavorites) setFavoriteProgramIds(JSON.parse(storedFavorites) as number[]);
    if (!stored) return;
    try {
      setPrefs({ ...DEFAULT_PREFS, ...(JSON.parse(stored) as Partial<HotelPrefs>) });
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

  const sortedPrograms = useMemo(() => sortPrograms(programs.filter((program) => program.kind === "hotel"), favoriteProgramIds), [favoriteProgramIds, programs]);
  const selectedQuote = useMemo(
    () => quotes.find((quote) => String(quote.id) === selectedQuoteId) || quotes[0],
    [quotes, selectedQuoteId],
  );
  const winner = evaluation?.options.find((option) => option.rank === 1) || null;

  async function loadPage() {
    try {
      const [nextPrograms, nextQuotes] = await Promise.all([listPrograms(), listHotelStayQuotes()]);
      const storedFavorites = window.localStorage.getItem(FAVORITE_PROGRAM_PREF_KEY);
      const nextFavorites = storedFavorites ? JSON.parse(storedFavorites) as number[] : defaultFavoriteProgramIds(nextPrograms);
      if (!storedFavorites) window.localStorage.setItem(FAVORITE_PROGRAM_PREF_KEY, JSON.stringify(nextFavorites));
      setFavoriteProgramIds(nextFavorites);
      setPrograms(nextPrograms);
      setQuotes(nextQuotes);
      if (!prefs.programId) {
        const firstHotel = sortPrograms(nextPrograms.filter((program) => program.kind === "hotel"), nextFavorites)[0];
        if (firstHotel) setPrefs((current) => ({ ...current, programId: String(firstHotel.id) }));
      }
      setSelectedQuoteId(selectedQuoteId || String(nextQuotes[0]?.id || ""));
      setError(null);
    } catch {
      setError("住宿比價資料載入失敗，請稍後再試。");
    }
  }

  async function submitAndEvaluate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      const quote = await createHotelStayQuote({
        owner: field(data, "owner"),
        hotel_name: field(data, "hotel_name"),
        stay_date: field(data, "stay_date"),
        nights: Number(field(data, "nights") || "1"),
        program_id: Number(field(data, "program_id")),
        cash_price_twd: field(data, "cash_price_twd"),
        points_price_per_night: field(data, "points_price_per_night"),
        taxes_note: field(data, "taxes_note") || null,
        topup_allowed: field(data, "topup_allowed") === "on",
        topup_points: field(data, "topup_points") || null,
      });
      const result = await evaluateHotelStayQuote(quote.id);
      setSelectedQuoteId(String(quote.id));
      setEvaluation(result);
      setStatus("已完成住宿比價；這不會消耗點數，也不會標記免房券。");
      await loadPage();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "住宿比價失敗，請確認欄位。");
    }
  }

  async function evaluateSelected() {
    if (!selectedQuote) return;
    try {
      setEvaluation(await evaluateHotelStayQuote(selectedQuote.id));
      setStatus("已重新評估住宿比價；資料仍保持唯讀。");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "重新評估失敗。");
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
          <span>住宿比價</span>
        </nav>

        <section className="page-header">
          <div>
            <div className="section-kicker">住宿比價</div>
            <h1>現金、點數、免房券，放在同一張桌上算</h1>
            <p>輸入現金價與每晚點數價，比較現金、純點數、免房券、券加補點四種方案。</p>
          </div>
          <Link className="button" href="/wallet">回點數錢包</Link>
        </section>

        {error ? <div className="notice notice-error">{error}</div> : null}
        {status ? <p className="subtle">{status}</p> : null}

        <form className="panel" onSubmit={submitAndEvaluate}>
          <h2>新增住宿比價</h2>
          <div className={styles.awardLine}>
            <select name="owner" value={prefs.owner} onChange={(event) => setPrefs({ ...prefs, owner: event.target.value as "kent" | "wife" })}>
              <option value="kent">凱章</option>
              <option value="wife">老婆</option>
            </select>
            <input name="hotel_name" placeholder="飯店名稱" required />
            <input name="stay_date" type="date" required />
            <input name="nights" placeholder="晚數" defaultValue="1" inputMode="numeric" required />
            <select name="program_id" value={prefs.programId} onChange={(event) => setPrefs({ ...prefs, programId: event.target.value })} required>
              <option value="">飯店計畫</option>
              {sortedPrograms.map((program) => <option key={program.id} value={program.id}>{programDisplayName(program, favoriteProgramIds)}</option>)}
            </select>
            <input name="cash_price_twd" placeholder="現金價 NT$" inputMode="decimal" required />
            <input name="points_price_per_night" placeholder="每晚點數價" inputMode="numeric" required />
            <input name="topup_points" placeholder="每晚補點上限" inputMode="numeric" />
            <label className={styles.checkboxLine}>
              <input name="topup_allowed" type="checkbox" /> 允許券加補點
            </label>
            <input name="taxes_note" placeholder="稅費或備註" />
            <button className="button button-primary" type="submit">幫我比價</button>
          </div>
        </form>

        <section className="panel">
          <div className={styles.sectionHeader}>
            <div>
              <h2>既有住宿需求</h2>
              <p className="subtle">quote 會保存；比較結果即時計算，不落庫。</p>
            </div>
            <button className="button" type="button" onClick={evaluateSelected} disabled={!selectedQuote}>重新評估</button>
          </div>
          <select value={selectedQuote ? String(selectedQuote.id) : ""} onChange={(event) => setSelectedQuoteId(event.target.value)}>
            {quotes.length === 0 ? <option value="">目前沒有住宿需求</option> : null}
            {quotes.map((quote) => <option key={quote.id} value={quote.id}>{quoteLabel(quote)}</option>)}
          </select>
        </section>

        {evaluation ? (
          <>
            <section className={styles.winnerPanel}>
              <div>
                <div className="section-kicker">每點價值</div>
                <h2>{evaluation.quote.hotel_name}：{Number(evaluation.cpp).toLocaleString("zh-TW", { minimumFractionDigits: 3, maximumFractionDigits: 3 })} 元/點</h2>
                <p>總點數 {formatNumber(evaluation.total_points)}；機會成本尚未自動化，請自行心算。</p>
              </div>
              <strong>{winner ? `首選：${winner.label}` : "尚無可用方案"}</strong>
            </section>

            <section className="panel">
              <h2>四種支付方式</h2>
              <div className={styles.hotelOptionList}>
                {evaluation.options.map((option) => (
                  <OptionCard key={option.method} option={option} />
                ))}
              </div>
              {evaluation.notes.map((note) => <p className="subtle" key={note}>{note}</p>)}
            </section>
          </>
        ) : (
          <section className="panel">
            <h2>比價結果</h2>
            <p className="pending-text">建立或選擇住宿需求後，這裡會顯示四種方案。</p>
          </section>
        )}
      </div>
    </main>
  );
}

function OptionCard({ option }: { option: HotelStayOption }) {
  const recommended = option.rank === 1;
  return (
    <article className={`${styles.hotelOptionCard} ${recommended ? styles.recommendedHotelOption : ""}`}>
      <div className={styles.hotelOptionIdentity}>
        <div className="section-kicker">{recommended ? "♛ 推薦方案" : option.rank ? `排名 #${option.rank}` : "不列入排名"}</div>
        <h3>{option.label}</h3>
        <p className="subtle">用券 {option.nights_with_voucher} 晚 · 點數 {option.nights_with_points} 晚 · 消耗 {formatNumber(option.points_consumed)} 點</p>
        {option.notes.map((note) => <small className="subtle" key={note}>{note}</small>)}
      </div>
      <div className={styles.hotelOptionPrice}>
        <span>{option.available ? "總成本" : "目前狀態"}</span>
        <strong>{option.available ? formatMoney(option.cash_cost_twd) : "不可用"}</strong>
        {recommended ? <small>目前成本最低</small> : null}
      </div>
    </article>
  );
}

function field(data: FormData, name: string): string {
  const value = data.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function quoteLabel(quote: HotelStayQuote): string {
  return `${OWNER_LABELS[quote.owner] || quote.owner} · ${quote.hotel_name} · ${quote.stay_date} · ${quote.nights} 晚`;
}

function formatMoney(value: string | number | null): string {
  const numberValue = Number(value || 0);
  return `NT$${numberValue.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}`;
}

function formatNumber(value: string | number | null): string {
  return Number(value || 0).toLocaleString("zh-TW", { maximumFractionDigits: 2 });
}
