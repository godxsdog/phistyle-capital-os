"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { PageHeader } from "../../../components/ui";
import {
  KnowledgeDocument,
  DestRegion,
  Program,
  RouteSweetSpot,
  getKnowledgeDocument,
  getRouteAdvisor,
  listPrograms,
  listDestRegions,
  listRouteSweetSpots,
  transitionRouteSweetSpot,
  updateRouteSweetSpot,
  upsertDestRegion,
} from "../../../lib/walletApi";
import styles from "./AdvisorPage.module.css";

const CABIN_LABELS: Record<string, string> = { economy: "經濟艙", premium: "豪華經濟艙", business: "商務艙", first: "頭等艙" };

export default function RouteAdvisorPage() {
  const [destination, setDestination] = useState("NRT");
  const [includeAi, setIncludeAi] = useState(false);
  const [recommendations, setRecommendations] = useState<RouteSweetSpot[]>([]);
  const [aiAdvice, setAiAdvice] = useState<string | null>(null);
  const [pending, setPending] = useState<RouteSweetSpot[]>([]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [sources, setSources] = useState<Record<number, KnowledgeDocument>>({});
  const [regions, setRegions] = useState<DestRegion[]>([]);
  const [regionAirport, setRegionAirport] = useState("");
  const [regionName, setRegionName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadPending() {
    const [rows, programRows, regionRows] = await Promise.all([listRouteSweetSpots("未確認"), listPrograms(), listDestRegions()]);
    setPending(rows);
    setPrograms(programRows.filter((program) => program.kind === "airline"));
    setRegions(regionRows);
  }

  useEffect(() => { void loadPending().catch((exc) => setError(exc instanceof Error ? exc.message : "讀取待確認資料失敗。")); }, []);

  async function search(event: FormEvent) {
    event.preventDefault();
    setLoading(true); setError(null); setMessage(null);
    try {
      const result = await getRouteAdvisor(destination.trim().toUpperCase(), includeAi);
      setRecommendations(result.recommendations);
      setAiAdvice(result.ai_advice);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "查詢失敗。");
    } finally { setLoading(false); }
  }

  async function save(row: RouteSweetSpot, form: HTMLFormElement) {
    const data = new FormData(form);
    try {
      await updateRouteSweetSpot(row.id, {
        program_id: Number(data.get("program_id")), origin_tag: "TPE",
        dest_tag: String(data.get("dest_tag") || ""), cabin: String(data.get("cabin") || ""),
        miles_cost: String(data.get("miles_cost") || "") || null,
        tip: String(data.get("tip") || ""), caveats: String(data.get("caveats") || "") || null,
      });
      await loadPending(); setMessage("候選內容已更新，仍維持未確認狀態。");
    } catch (exc) { setError(exc instanceof Error ? exc.message : "儲存失敗。"); }
  }

  async function transition(id: number, status: "已確認" | "已否決") {
    try { await transitionRouteSweetSpot(id, status); await loadPending(); setMessage(status === "已確認" ? "甜點已確認，可進入顧問結果。" : "甜點已否決並保留紀錄。"); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "狀態更新失敗。"); }
  }

  async function toggleSource(documentId: number) {
    if (sources[documentId]) { setSources((current) => { const next = { ...current }; delete next[documentId]; return next; }); return; }
    try { const document = await getKnowledgeDocument(documentId); setSources((current) => ({ ...current, [documentId]: document })); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "讀取攻略出處失敗。"); }
  }

  async function saveRegion(event: FormEvent) {
    event.preventDefault();
    try {
      await upsertDestRegion(regionAirport.trim().toUpperCase(), regionName.trim());
      await loadPending(); setRegionAirport(""); setRegionName(""); setMessage("目的地區域已更新。");
    } catch (exc) { setError(exc instanceof Error ? exc.message : "區域更新失敗。"); }
  }

  return <main><div className="shell">
    <nav className="breadcrumb" aria-label="麵包屑"><Link href="/">PhiStyle OS</Link><span>/</span><Link href="/wallet">點數錢包</Link><span>/</span><span>里程顧問</span></nav>
    <PageHeader kicker="Point Wallet" title="目的地里程顧問" description="從已經人工確認的攻略中，找出由台北出發的里程甜點。" />
    {error ? <div className="notice notice-error">{error}</div> : null}{message ? <div className="notice">{message}</div> : null}
    <form className={`${styles.searchBar} panel`} onSubmit={search}>
      <label><span>目的地機場</span><input value={destination} maxLength={3} onChange={(event) => setDestination(event.target.value.toUpperCase())} required /></label>
      <label><span>AI 綜合建議</span><input type="checkbox" checked={includeAi} onChange={(event) => setIncludeAi(event.target.checked)} /></label>
      <button className="button button-primary" disabled={loading} type="submit">{loading ? "查詢中..." : "查詢甜點"}</button>
    </form>

    <section className="panel"><div className="stage-header"><div><h2>已確認推薦</h2><p className="subtle">直達機場與所屬區域一併匹配，依所需哩程排序。</p></div><span className="stage-pill">TPE 出發</span></div>
      {recommendations.length ? <div className={styles.resultList}>{recommendations.map((row) => <article className={styles.resultCard} key={row.id}><div className={styles.program}><strong>{row.program_name}</strong><span>{CABIN_LABELS[row.cabin] || row.cabin} · {row.dest_tag}</span></div><div><strong>{row.tip}</strong>{row.caveats ? <p>{row.caveats}</p> : null}<button className="button" type="button" onClick={() => void toggleSource(row.source_doc_id)}>查證：{row.source_title}</button>{sources[row.source_doc_id] ? <div className={styles.sourcePanel}><div className={styles.sourceContent}>{sources[row.source_doc_id].content}</div></div> : null}</div><div className={styles.miles}><strong>{row.miles_cost ? Number(row.miles_cost).toLocaleString("zh-TW") : "未標價"}</strong><span>{row.miles_cost ? "哩" : "請查原文"}</span></div></article>)}</div> : <p className="pending-text">尚無符合目的地的已確認甜點。</p>}
      {aiAdvice ? <div className={styles.aiPanel}><h3>AI 綜合建議</h3>{aiAdvice}</div> : null}
    </section>

    <section className="panel"><div className="stage-header"><div><h2>待確認</h2><p className="subtle">AI 萃取內容不會自動生效；請逐筆核對攻略原文。</p></div><span className="stage-pill">{pending.length} 筆</span></div>
      <div className={styles.reviewList}>{pending.map((row) => <PendingEditor key={row.id} row={row} programs={programs} source={sources[row.source_doc_id]} onSource={() => void toggleSource(row.source_doc_id)} onSave={save} onTransition={transition} />)}{pending.length === 0 ? <p className="pending-text">目前沒有待確認候選。</p> : null}</div>
    </section>

    <section className="panel"><h2>新增攻略流程</h2><div className={styles.guideFlow}><span>放入 guides/</span><span>→</span><span>執行匯入 dry-run</span><span>→</span><span>解析預覽</span><span>→</span><span>人工確認</span></div></section>
    <details className="panel"><summary>目的地區域設定（{regions.length} 個機場）</summary><form className={styles.regionForm} onSubmit={saveRegion}><label><span>機場碼</span><input value={regionAirport} maxLength={3} onChange={(event) => setRegionAirport(event.target.value.toUpperCase())} required /></label><label><span>區域名稱</span><input value={regionName} onChange={(event) => setRegionName(event.target.value)} required /></label><button className="button" type="submit">新增或更新</button></form><div className={styles.regionList}>{regions.map((region) => <button className="button" key={region.airport} type="button" onClick={() => { setRegionAirport(region.airport); setRegionName(region.region); }}>{region.airport} · {region.region}</button>)}</div></details>
  </div></main>;
}

function PendingEditor({ row, programs, source, onSource, onSave, onTransition }: { row: RouteSweetSpot; programs: Program[]; source?: KnowledgeDocument; onSource: () => void; onSave: (row: RouteSweetSpot, form: HTMLFormElement) => Promise<void>; onTransition: (id: number, status: "已確認" | "已否決") => Promise<void> }) {
  return <article className={styles.reviewCard}><form className={styles.reviewGrid} onSubmit={(event) => { event.preventDefault(); void onSave(row, event.currentTarget); }}>
    <label><span>計畫</span><select name="program_id" defaultValue={row.program_id}>{programs.map((program) => <option key={program.id} value={program.id}>{program.name}</option>)}</select></label>
    <label><span>目的地標籤</span><input name="dest_tag" defaultValue={row.dest_tag} required /></label>
    <label><span>艙等</span><select name="cabin" defaultValue={row.cabin}><option value="economy">經濟艙</option><option value="premium">豪華經濟艙</option><option value="business">商務艙</option><option value="first">頭等艙</option></select></label>
    <label><span>所需哩程</span><input name="miles_cost" defaultValue={row.miles_cost || ""} inputMode="numeric" /></label>
    <label className={styles.wideField}><span>甜點摘要</span><input name="tip" defaultValue={row.tip} required /></label>
    <label className={styles.wideField}><span>限制與提醒</span><textarea name="caveats" defaultValue={row.caveats || ""} rows={2} /></label>
    <div className={styles.actions}><button className="button" type="submit">儲存修改</button><button className="button" type="button" onClick={onSource}>查證：{row.source_title}</button><button className="button button-primary" type="button" onClick={() => void onTransition(row.id, "已確認")}>確認</button><button className="button" type="button" onClick={() => void onTransition(row.id, "已否決")}>否決</button></div>
  </form>{source ? <div className={styles.sourcePanel}><div className={styles.sourceContent}>{source.content}</div></div> : null}</article>;
}
