"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Account,
  ExpiryAlert,
  FxRate,
  HotelVoucher,
  Portfolio,
  Program,
  TransferRule,
  WalletAiParsedRule,
  createAccount,
  createHotelVoucher,
  createLedger,
  createProgram,
  createPurchaseOffer,
  createTransferRule,
  deleteTransferRule,
  getPortfolio,
  listHotelVouchers,
  listExpiryAlerts,
  listFxRates,
  listAccounts,
  listPrograms,
  listTransferRules,
  parseWalletRuleWithAi,
  refreshFxRates,
  scanExpiryAlerts,
  updateHotelVoucherStatus,
  updateTransferRule,
} from "../../lib/walletApi";
import {
  CURRENCY_OPTIONS,
  KIND_LABELS,
  LEDGER_KIND_OPTIONS,
  OWNER_LABELS,
  PROGRAM_KIND_OPTIONS,
  TAB_LABELS,
  WalletTab,
} from "./constants";
import {
  FAVORITE_PROGRAM_PREF_KEY,
  defaultFavoriteProgramIds,
  findProgramByAliases,
  programDisplayName,
  sortPrograms,
} from "./programPreferences";
import styles from "./WalletPage.module.css";

const PREF_KEY = "phistyle.wallet.source.preferences";
const COST_PREF_KEY = "phistyle.wallet.manualCost";
const PINNED_PREF_KEY = "phistyle.wallet.pinnedSources";

type Preferences = {
  tab: WalletTab;
  owner: "kent" | "wife";
  programId: string;
  kind: string;
  currency: string;
  targetProgramId: string;
};

type EditableRule = {
  from_program_id: string;
  to_program_id: string;
  ratio_from: string;
  ratio_to: string;
  bonus_pct: string;
  min_transfer: string;
  valid_from: string;
  valid_until: string;
  transfer_days_note: string;
  rule_kind: string;
  block_size: string;
  block_bonus_points: string;
  source_url: string;
};

type ManualCosts = Record<string, string>;

const DEFAULT_PREFS: Preferences = {
  tab: "overview",
  owner: "kent",
  programId: "",
  kind: "adjustment",
  currency: "TWD",
  targetProgramId: "",
};

const PRIMARY_SOURCE_TABS: Array<{ tab: WalletTab; aliases: string[] }> = [
  { tab: "wanlitong", aliases: ["萬里通", "平安萬里通"] },
  { tab: "marriott", aliases: ["萬豪", "Marriott"] },
  { tab: "juneyao", aliases: ["吉祥", "Juneyao"] },
];

export default function WalletPage() {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS);
  const [manualCosts, setManualCosts] = useState<ManualCosts>({});
  const [pinnedSources, setPinnedSources] = useState<number[]>([]);
  const [favoriteProgramIds, setFavoriteProgramIds] = useState<number[]>([]);
  const [favoritePrefsReady, setFavoritePrefsReady] = useState(false);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [rules, setRules] = useState<TransferRule[]>([]);
  const [portfolioAll, setPortfolioAll] = useState<Portfolio | null>(null);
  const [portfolioKent, setPortfolioKent] = useState<Portfolio | null>(null);
  const [portfolioWife, setPortfolioWife] = useState<Portfolio | null>(null);
  const [expiryAlerts, setExpiryAlerts] = useState<ExpiryAlert[]>([]);
  const [hotelVouchers, setHotelVouchers] = useState<HotelVoucher[]>([]);
  const [fxRates, setFxRates] = useState<FxRate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    loadStoredPrefs();
    void loadWallet();
  }, []);

  useEffect(() => {
    window.localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
  }, [prefs]);

  useEffect(() => {
    window.localStorage.setItem(COST_PREF_KEY, JSON.stringify(manualCosts));
  }, [manualCosts]);

  useEffect(() => {
    window.localStorage.setItem(PINNED_PREF_KEY, JSON.stringify(pinnedSources));
  }, [pinnedSources]);

  useEffect(() => {
    if (!favoritePrefsReady) return;
    window.localStorage.setItem(FAVORITE_PROGRAM_PREF_KEY, JSON.stringify(favoriteProgramIds));
  }, [favoritePrefsReady, favoriteProgramIds]);

  const sortedPrograms = useMemo(() => sortPrograms(programs, favoriteProgramIds), [favoriteProgramIds, programs]);

  const sourcePrograms = useMemo(() => {
    const sourceIds = Array.from(new Set(rules.map((rule) => rule.from_program_id)));
    return sortPrograms(
      programs.filter((program) => sourceIds.includes(program.id) || pinnedSources.includes(program.id)),
      favoriteProgramIds,
    );
  }, [favoriteProgramIds, pinnedSources, programs, rules]);

  const activeSourceProgram = useMemo(() => {
    const primary = PRIMARY_SOURCE_TABS.find((item) => item.tab === prefs.tab);
    if (primary) return findProgramByAliases(programs, primary.aliases);
    return null;
  }, [prefs.tab, programs]);

  async function loadWallet() {
    try {
      const [nextPrograms, nextAccounts, nextRules, nextPortfolioAll, nextPortfolioKent, nextPortfolioWife, nextExpiryAlerts, nextHotelVouchers, nextFxRates] = await Promise.all([
        listPrograms(),
        listAccounts(),
        listTransferRules(),
        getPortfolio(),
        getPortfolio("kent"),
        getPortfolio("wife"),
        listExpiryAlerts(),
        listHotelVouchers(),
        listFxRates(),
      ]);
      if (!window.localStorage.getItem(FAVORITE_PROGRAM_PREF_KEY)) {
        setFavoriteProgramIds(defaultFavoriteProgramIds(nextPrograms));
        setFavoritePrefsReady(true);
      }
      setPrograms(nextPrograms);
      setAccounts(nextAccounts);
      setRules(nextRules);
      setPortfolioAll(nextPortfolioAll);
      setPortfolioKent(nextPortfolioKent);
      setPortfolioWife(nextPortfolioWife);
      setExpiryAlerts(nextExpiryAlerts);
      setHotelVouchers(nextHotelVouchers);
      setFxRates(nextFxRates);
      setError(null);
    } catch {
      setError("資料載入失敗，請稍後再試。");
    }
  }

  async function submit(action: () => Promise<unknown>, message: string) {
    try {
      await action();
      setStatus(message);
      setError(null);
      await loadWallet();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "儲存失敗，請確認欄位後再試。");
    }
  }

  function loadStoredPrefs() {
    try {
      const storedPrefs = window.localStorage.getItem(PREF_KEY);
      if (storedPrefs) setPrefs({ ...DEFAULT_PREFS, ...(JSON.parse(storedPrefs) as Partial<Preferences>) });
      const storedCosts = window.localStorage.getItem(COST_PREF_KEY);
      if (storedCosts) setManualCosts(JSON.parse(storedCosts) as ManualCosts);
      const storedPinned = window.localStorage.getItem(PINNED_PREF_KEY);
      if (storedPinned) setPinnedSources(JSON.parse(storedPinned) as number[]);
      const storedFavorites = window.localStorage.getItem(FAVORITE_PROGRAM_PREF_KEY);
      if (storedFavorites) {
        setFavoriteProgramIds(JSON.parse(storedFavorites) as number[]);
        setFavoritePrefsReady(true);
      }
    } catch {
      window.localStorage.removeItem(PREF_KEY);
      window.localStorage.removeItem(COST_PREF_KEY);
      window.localStorage.removeItem(PINNED_PREF_KEY);
      window.localStorage.removeItem(FAVORITE_PROGRAM_PREF_KEY);
    }
    // Deep-link support so other pages (e.g. the launcher's 轉點規則 tile) can
    // open a specific wallet tab directly, e.g. /wallet?tab=wanlitong.
    const requestedTab = new URLSearchParams(window.location.search).get("tab");
    if (requestedTab && (Object.keys(TAB_LABELS) as string[]).includes(requestedTab)) {
      updatePrefs({ tab: requestedTab as WalletTab });
    }
  }

  function updatePrefs(next: Partial<Preferences>) {
    setPrefs((current) => ({ ...current, ...next }));
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="麵包屑">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>點數錢包</span>
        </nav>

        <section className="page-header">
          <div>
            <div className="section-kicker">點數錢包</div>
            <h1>來源計畫視角</h1>
            <p>每個來源計畫都是一頁完整世界：成本、餘額、兌換表、AI 解析與快速試算都放在同一處。</p>
          </div>
          <button className="button" type="button" onClick={() => submit(refreshFxRates, "匯率已更新；若外部服務失敗則使用備用匯率。")}>
            更新匯率
          </button>
          <Link className="button button-primary" href="/wallet/awards">
            換票比價
          </Link>
        </section>

        <div className={styles.primaryNav} role="tablist" aria-label="點數錢包導覽">
          {(Object.keys(TAB_LABELS) as WalletTab[]).map((tab) => (
            <button
              key={tab}
              className={`button ${prefs.tab === tab ? "button-primary" : ""}`}
              type="button"
              onClick={() => updatePrefs({ tab })}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
          <Link className="button" href="/wallet/awards">換票比價</Link>
        </div>

        {error ? <div className="notice notice-error">{error}</div> : null}
        {status ? <p className="subtle">{status}</p> : null}

        {prefs.tab === "overview" ? (
          <OverviewPanel
            programs={sortedPrograms}
            sourcePrograms={sourcePrograms}
            portfolio={portfolioAll}
            kent={portfolioKent}
            wife={portfolioWife}
            favoriteProgramIds={favoriteProgramIds}
            expiryAlerts={expiryAlerts}
            setFavoriteProgramIds={setFavoriteProgramIds}
            openSource={(program) => {
              setPinnedSources((current) => (current.includes(program.id) ? current : [...current, program.id]));
              updatePrefs({ tab: primaryTabForProgram(program) || "otherSources" });
            }}
            scanExpiry={() => submit(scanExpiryAlerts, "到期提醒已掃描；提醒只顯示在儀表板。")}
          />
        ) : null}

        {activeSourceProgram ? (
          <SourceProgramPanel
            program={activeSourceProgram}
            programs={sortedPrograms}
            favoriteProgramIds={favoriteProgramIds}
            rules={sortRulesByTargetProgram(rules.filter((rule) => rule.from_program_id === activeSourceProgram.id), sortedPrograms)}
            portfolioAll={portfolioAll}
            manualCost={manualCosts[String(activeSourceProgram.id)] || ""}
            setManualCost={(value) => setManualCosts((current) => ({ ...current, [String(activeSourceProgram.id)]: value }))}
            prefs={prefs}
            updatePrefs={updatePrefs}
            submit={submit}
            cnyRate={latestFxRate(fxRates, "CNY")}
          />
        ) : null}

        {prefs.tab !== "overview" && prefs.tab !== "otherSources" && prefs.tab !== "points" && !activeSourceProgram ? (
          <section className="panel">
            <h2>{TAB_LABELS[prefs.tab]}</h2>
            <p className="pending-text">目前還沒有找到這個來源計畫。請先在「我的點數」新增計畫，或到「其他來源」釘選已存在的來源。</p>
          </section>
        ) : null}

        {prefs.tab === "otherSources" ? (
          <OtherSourcesPanel
            programs={sortedPrograms}
            sourcePrograms={sourcePrograms}
            pinnedSources={pinnedSources}
            favoriteProgramIds={favoriteProgramIds}
            setPinnedSources={setPinnedSources}
          />
        ) : null}

        {prefs.tab === "points" ? (
          <MyPointsPanel
            sortedPrograms={sortedPrograms}
            favoriteProgramIds={favoriteProgramIds}
            accounts={accounts}
            hotelVouchers={hotelVouchers}
            portfolio={portfolioAll}
            prefs={prefs}
            updatePrefs={updatePrefs}
            submit={submit}
          />
        ) : null}
      </div>
    </main>
  );
}

function OverviewPanel({
  programs,
  sourcePrograms,
  portfolio,
  kent,
  wife,
  favoriteProgramIds,
  expiryAlerts,
  setFavoriteProgramIds,
  openSource,
  scanExpiry,
}: {
  programs: Program[];
  sourcePrograms: Program[];
  portfolio: Portfolio | null;
  kent: Portfolio | null;
  wife: Portfolio | null;
  favoriteProgramIds: number[];
  expiryAlerts: ExpiryAlert[];
  setFavoriteProgramIds: (value: number[] | ((current: number[]) => number[])) => void;
  openSource: (program: Program) => void;
  scanExpiry: () => Promise<void>;
}) {
  const [showFavorites, setShowFavorites] = useState(false);
  return (
    <>
      <section className={`${styles.walletHero} panel`}>
        <div className={styles.sectionHeader}>
          <div>
            <div className="section-kicker">點數資產總覽</div>
            <p className={styles.totalValue}>{formatMoney(portfolio?.total_real_cost_basis_twd)}</p>
            <p className="subtle">兩人合計真實成本 · 常用計畫會優先排列</p>
          </div>
          <button className="button" type="button" onClick={() => setShowFavorites((value) => !value)}>
            ⭐常用設定
          </button>
        </div>
        <div className={styles.summaryStrip}>
          <div>
            <span>凱章</span>
            <strong>{formatMoney(kent?.total_real_cost_basis_twd)}</strong>
          </div>
          <div>
            <span>老婆</span>
            <strong>{formatMoney(wife?.total_real_cost_basis_twd)}</strong>
          </div>
          <div>
            <span>來源計畫</span>
            <strong>{sourcePrograms.length} 個</strong>
          </div>
        </div>
        {showFavorites ? (
          <FavoriteSettings programs={programs} favoriteProgramIds={favoriteProgramIds} setFavoriteProgramIds={setFavoriteProgramIds} />
        ) : null}
      </section>

      <WalletAccountGroups
        portfolio={portfolio}
        programs={programs}
        favoriteProgramIds={favoriteProgramIds}
        openSource={openSource}
      />

      <section className="panel">
        <div className={styles.sectionHeader}>
          <div>
            <h2>到期提醒</h2>
            <p className="subtle">每日掃描 90 / 60 / 30 / 7 天門檻；本階段只在儀表板提醒，不寄信不傳 LINE。</p>
          </div>
          <button className="button" type="button" onClick={scanExpiry}>
            掃描到期
          </button>
        </div>
        {expiryAlerts.length === 0 ? (
          <p className="pending-text">目前沒有到期提醒。</p>
        ) : (
          <div className={styles.alertList}>
            {expiryAlerts.slice(0, 8).map((alert) => (
              <article className={styles.alertItem} key={alert.id}>
                <strong>{alert.threshold_days} 天</strong>
                <span>{alert.message}</span>
                <small>餘額 {formatNumber(alert.balance)}，檢查日 {alert.checked_on}</small>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <h2>來源計畫</h2>
        <div className={styles.sourceGrid}>
          {sourcePrograms.map((program) => (
            <article className={styles.sourceCard} key={program.id}>
              <h3>{programDisplayName(program, favoriteProgramIds)}</h3>
              <p>{KIND_LABELS.programKind[program.kind] || program.kind}</p>
              <button className="button" type="button" onClick={() => openSource(program)}>
                開啟來源頁
              </button>
            </article>
          ))}
          {sourcePrograms.length === 0 ? <p className="pending-text">目前還沒有任何來源計畫。</p> : null}
        </div>
      </section>

      <section className="panel">
        <h2>全部計畫</h2>
        <Table
          columns={["計畫", "類型", "到期規則"]}
          rows={programs.map((program) => [
            programDisplayName(program, favoriteProgramIds),
            KIND_LABELS.programKind[program.kind] || program.kind,
            program.expiry_rule_note || "未設定",
          ])}
        />
      </section>
    </>
  );
}

function FavoriteSettings({
  programs,
  favoriteProgramIds,
  setFavoriteProgramIds,
}: {
  programs: Program[];
  favoriteProgramIds: number[];
  setFavoriteProgramIds: (value: number[] | ((current: number[]) => number[])) => void;
}) {
  return (
    <div className={styles.favoriteSettings}>
      {programs.map((program) => (
        <label className={styles.favoriteOption} key={program.id}>
          <input
            type="checkbox"
            checked={favoriteProgramIds.includes(program.id)}
            onChange={(event) => {
              setFavoriteProgramIds((current) => (
                event.target.checked
                  ? [...current, program.id]
                  : current.filter((id) => id !== program.id)
              ));
            }}
          />
          <span>{programDisplayName(program, favoriteProgramIds)}</span>
          <small>{KIND_LABELS.programKind[program.kind] || program.kind}</small>
        </label>
      ))}
    </div>
  );
}

function WalletAccountGroups({
  portfolio,
  programs,
  favoriteProgramIds,
  openSource,
}: {
  portfolio: Portfolio | null;
  programs: Program[];
  favoriteProgramIds: number[];
  openSource: (program: Program) => void;
}) {
  const rows = portfolio?.accounts || [];
  return (
    <section className="panel">
      <div className={styles.sectionHeader}>
        <div>
          <h2>我的計畫</h2>
          <p className="subtle">依持有人分組，餘額與到期日放在同一眼可讀的位置。</p>
        </div>
      </div>
      {["kent", "wife"].map((owner) => {
        const ownerRows = rows.filter((row) => row.owner === owner);
        return (
          <div className={styles.ownerGroup} key={owner}>
            <h3>{OWNER_LABELS[owner] || owner}</h3>
            {ownerRows.length === 0 ? <p className="pending-text">目前沒有計畫。</p> : null}
            {ownerRows.map((row) => {
              const program = programs.find((item) => item.id === Number(row.program_id));
              const name = String(row.program_name || program?.name || "未命名計畫");
              const expiresAt = row.expires_at ? String(row.expires_at) : null;
              const daysLeft = expiresAt ? daysUntil(expiresAt) : null;
              return (
                <button
                  className={styles.programBalanceRow}
                  key={String(row.account_id)}
                  onClick={() => program && openSource(program)}
                  type="button"
                >
                  <span className={styles.programMonogram}>{programInitial(name)}</span>
                  <span className={styles.programIdentity}>
                    <strong>{favoriteLabelFromName(name, favoriteProgramIds, Number(row.program_id))}</strong>
                    <small>{program ? KIND_LABELS.programKind[program.kind] || program.kind : "點數計畫"}</small>
                  </span>
                  <strong className={styles.programBalance}>{formatInteger(row.balance)} 點</strong>
                  <span className={`${styles.expiryCountdown} ${daysLeft !== null && daysLeft <= 90 ? styles.expiryUrgent : ""}`}>
                    {daysLeft === null ? "未設定到期" : daysLeft < 0 ? "已到期" : `剩 ${daysLeft} 天`}
                    {expiresAt ? <small>{expiresAt.replaceAll("-", "/")}</small> : null}
                  </span>
                </button>
              );
            })}
          </div>
        );
      })}
    </section>
  );
}

function WanlitongPurchasePanel({
  program,
  cnyRate,
  submit,
}: {
  program: Program;
  cnyRate: FxRate | null;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  const [paidAmount, setPaidAmount] = useState("950");
  const [pointsReceived, setPointsReceived] = useState("500000");
  const paid = Number(paidAmount || 0);
  const points = Number(pointsReceived || 0);
  const rate = Number(cnyRate?.twd_per_unit || 0);
  const preview = paid > 0 && points > 0 && rate > 0 ? (paid / points) * rate : null;
  const basePrice = paid > 0 && points > 0 ? paid / points : 0;

  return (
    <section className="panel">
      <div className={styles.sectionHeader}>
        <div>
          <h2>萬里通購入成本</h2>
          <p className="subtle">輸入實付人民幣與實收點數；預覽不會回傳或落庫。</p>
        </div>
        <span className="stage-pill">CNY/TWD {rate ? rate.toFixed(4) : "尚無匯率"}</span>
      </div>
      <div className={styles.purchasePreviewGrid}>
        <label><span>實付人民幣</span><input value={paidAmount} onChange={(event) => setPaidAmount(event.target.value)} inputMode="decimal" /></label>
        <label><span>實收萬里通點數</span><input value={pointsReceived} onChange={(event) => setPointsReceived(integerInput(event.target.value))} inputMode="numeric" /></label>
        <div className={styles.cppPreview}>
          <span>台幣每點成本預覽</span>
          <strong>{preview === null ? "等待輸入" : `≈ NT$${preview.toFixed(3)}/點`}</strong>
          <small>參考，以入庫值為準</small>
        </div>
        <button
          className="button button-primary"
          disabled={!basePrice || !rate}
          type="button"
          onClick={() => submit(() => createPurchaseOffer({
            program_id: program.id,
            kind: "official",
            base_price: String(basePrice),
            currency: "CNY",
            bonus_pct: "0",
            start_date: today(),
            paid_amount: paidAmount,
            fees: "0",
            rebate: "0",
            points_received: pointsReceived,
            source_note: "萬里通購入成本",
          }), "購入成本已儲存；入庫每點成本由後端計算。")}
        >
          儲存購入成本
        </button>
      </div>
    </section>
  );
}

function SourceProgramPanel({
  program,
  programs,
  favoriteProgramIds,
  rules,
  portfolioAll,
  manualCost,
  setManualCost,
  prefs,
  updatePrefs,
  submit,
  cnyRate,
}: {
  program: Program;
  programs: Program[];
  favoriteProgramIds: number[];
  rules: TransferRule[];
  portfolioAll: Portfolio | null;
  manualCost: string;
  setManualCost: (value: string) => void;
  prefs: Preferences;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
  cnyRate: FxRate | null;
}) {
  const [quickTargetId, setQuickTargetId] = useState("");
  const [quickQuantity, setQuickQuantity] = useState("30000");
  const cost = Number(manualCost || sourceAvgCost(portfolioAll, program.id) || 0);
  const balances = ownerBalances(portfolioAll, program.id);
  const targetPrograms = programs.filter((item) => rules.some((rule) => rule.to_program_id === item.id));
  const defaultTargetId = String(targetPrograms.find((item) => String(item.id) === prefs.targetProgramId)?.id || targetPrograms[0]?.id || "");
  const selectedQuickTargetId = quickTargetId || defaultTargetId;
  const activeQuickRule = rules.find((rule) => String(rule.to_program_id) === selectedQuickTargetId);
  const quick = activeQuickRule ? calculateRequiredSourcePoints(activeQuickRule, Number(quickQuantity || 0)) : null;

  return (
    <>
      <section className="panel">
        <div className={styles.sourceHero}>
          <div>
            <div className="section-kicker">來源計畫</div>
            <h2>{programDisplayName(program, favoriteProgramIds)}</h2>
            <p className="subtle">這一頁只回答：我有多少、每點成本多少、可以轉去哪裡、要送多少點才夠。</p>
          </div>
          <label className={styles.inlineField}>
            <span>每點成本 NT$</span>
            <input
              value={manualCost}
              onChange={(event) => setManualCost(event.target.value)}
              placeholder={sourceAvgCost(portfolioAll, program.id) || "手動輸入"}
              inputMode="decimal"
            />
          </label>
        </div>
        <div className="data-grid">
          <div>
            <dt>凱章餘額</dt>
            <dd>{formatNumber(balances.kent)}</dd>
          </div>
          <div>
            <dt>老婆餘額</dt>
            <dd>{formatNumber(balances.wife)}</dd>
          </div>
          <div>
            <dt>成本來源</dt>
            <dd>{manualCost ? "手動試算" : "成本批次平均"}</dd>
          </div>
          <div>
            <dt>可轉目的地</dt>
            <dd>{targetPrograms.length} 個</dd>
          </div>
        </div>
      </section>

      {isWanlitong(program) ? (
        <WanlitongPurchasePanel program={program} cnyRate={cnyRate} submit={submit} />
      ) : null}

      <section className="panel">
        <div className={styles.sectionHeader}>
          <div>
            <h2>完整兌換表</h2>
            <p className="subtle">比例一律是「送出 X：得到 Y」，列內即可編輯，不跳頁。</p>
          </div>
        </div>
        {rules.length === 0 ? (
          <div className={styles.emptyState}>
            <strong>+新增兌換規則</strong>
            <p>這個來源計畫目前沒有規則。可以手動新增，或貼促銷文字讓 AI 先整理成待確認預覽。</p>
          </div>
        ) : (
          <div className={styles.transferTable}>
            <div className={styles.transferHead}>
              <span>目標計畫</span>
              <span>比例</span>
              <span>加贈</span>
              <span>門檻規則</span>
              <span>試算</span>
              <span>操作</span>
            </div>
            {rules.map((rule) => (
              <TransferRuleRow
                key={rule.id}
                rule={rule}
                programs={programs}
                favoriteProgramIds={favoriteProgramIds}
                sourceCost={cost}
                submit={submit}
              />
            ))}
          </div>
        )}
      </section>

      <div className={styles.grid}>
        <TransferRuleCreatePanel
          program={program}
          programs={programs}
          favoriteProgramIds={favoriteProgramIds}
          selectedTargetProgramId={prefs.targetProgramId}
          updatePrefs={updatePrefs}
          submit={submit}
        />
        <AiParsePanel sourceProgram={program} programs={programs} favoriteProgramIds={favoriteProgramIds} submit={submit} />
      </div>

      <section className="panel">
        <h2>快速試算器</h2>
        <div className={styles.inlineCalc}>
          <span>我要</span>
          <select
            value={selectedQuickTargetId}
            onChange={(event) => {
              setQuickTargetId(event.target.value);
              updatePrefs({ targetProgramId: event.target.value });
            }}
          >
            {targetPrograms.length === 0 ? <option value="">沒有可用目的地</option> : null}
            {targetPrograms.map((item) => (
              <option key={item.id} value={item.id}>{programDisplayName(item, favoriteProgramIds)}</option>
            ))}
          </select>
          <input value={quickQuantity} onChange={(event) => setQuickQuantity(event.target.value)} inputMode="numeric" />
          <span>點</span>
        </div>
        {quick && activeQuickRule ? (
          <div className="data-grid">
            <div>
              <dt>需送出 {programDisplayName(program, favoriteProgramIds)}</dt>
              <dd>{formatNumber(quick.requiredSourcePoints)} 點</dd>
            </div>
            <div>
              <dt>使用規則</dt>
              <dd>{ruleRatioText(activeQuickRule)}</dd>
            </div>
            <div>
              <dt>總成本</dt>
              <dd>{formatMoney(quick.requiredSourcePoints * cost)}</dd>
            </div>
            <div>
              <dt>實得</dt>
              <dd>{formatNumber(quick.receivedPoints)} 點</dd>
            </div>
          </div>
        ) : (
          <p className="pending-text">請先新增至少一條兌換規則。</p>
        )}
      </section>
    </>
  );
}

function TransferRuleRow({
  rule,
  programs,
  favoriteProgramIds,
  sourceCost,
  submit,
}: {
  rule: TransferRule;
  programs: Program[];
  favoriteProgramIds: number[];
  sourceCost: number;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState<EditableRule>(() => editableRule(rule));
  const [targetPoints, setTargetPoints] = useState("30000");
  const calc = calculateRequiredSourcePoints(rule, Number(targetPoints || 0));

  useEffect(() => {
    setDraft(editableRule(rule));
  }, [rule]);

  function updateDraft(key: keyof EditableRule, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  return (
    <article className={styles.transferRow}>
      <div>
        <select value={draft.to_program_id} onChange={(event) => updateDraft("to_program_id", event.target.value)}>
          {programs.map((program) => (
            <option key={program.id} value={program.id}>{programDisplayName(program, favoriteProgramIds)}</option>
          ))}
        </select>
        {rule.source_url ? <a href={rule.source_url} target="_blank" rel="noreferrer">查證</a> : <span className="subtle">未填查證連結</span>}
      </div>
      <div className={styles.compactInputs}>
        <input value={integerInput(draft.ratio_from)} onChange={(event) => updateDraft("ratio_from", integerInput(event.target.value))} inputMode="numeric" aria-label="送出數量" />
        <span>:</span>
        <input value={integerInput(draft.ratio_to)} onChange={(event) => updateDraft("ratio_to", integerInput(event.target.value))} inputMode="numeric" aria-label="得到數量" />
      </div>
      <div className={styles.bonusField}><input value={draft.bonus_pct} onChange={(event) => updateDraft("bonus_pct", event.target.value)} inputMode="decimal" aria-label="加贈百分比" /><span>%</span></div>
      <div className={styles.compactInputs}>
        <select value={draft.rule_kind} onChange={(event) => updateDraft("rule_kind", event.target.value)}>
          <option value="linear">一般</option>
          <option value="threshold_block">滿額</option>
        </select>
        <input value={draft.block_size} onChange={(event) => updateDraft("block_size", event.target.value)} placeholder="滿額" />
        <input value={draft.block_bonus_points} onChange={(event) => updateDraft("block_bonus_points", event.target.value)} placeholder="送點" />
      </div>
      <div>
        <input value={targetPoints} onChange={(event) => setTargetPoints(event.target.value)} inputMode="numeric" aria-label="試算目標點數" />
        <p className="subtle">
          需送 {formatNumber(calc.requiredSourcePoints)}，成本 {formatMoney(calc.requiredSourcePoints * sourceCost)}
        </p>
      </div>
      <div className={styles.rowActions}>
        <button
          className="button button-primary"
          type="button"
          onClick={() => submit(() => updateTransferRule(rule.id, transferRulePayload(draft)), "兌換規則已更新。")}
        >
          儲存
        </button>
        <button className="button" type="button" onClick={() => submit(() => deleteTransferRule(rule.id), "兌換規則已刪除。")}>
          刪除
        </button>
      </div>
    </article>
  );
}

function TransferRuleCreatePanel({
  program,
  programs,
  favoriteProgramIds,
  selectedTargetProgramId,
  updatePrefs,
  submit,
}: {
  program: Program;
  programs: Program[];
  favoriteProgramIds: number[];
  selectedTargetProgramId: string;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  const targetPrograms = programs.filter((item) => item.id !== program.id);
  const selectedId = String(targetPrograms.find((item) => String(item.id) === selectedTargetProgramId)?.id || targetPrograms[0]?.id || "");
  return (
    <FormPanel title="+新增兌換規則" description="手動新增一條來源計畫規則；比例請填送出數量與實得數量。">
      {(form) => (
        <>
          <select
            name="to_program_id"
            value={selectedId}
            onChange={(event) => updatePrefs({ targetProgramId: event.target.value })}
            required
          >
            <option value="">選擇目標計畫</option>
            {targetPrograms.map((item) => (
              <option key={item.id} value={item.id}>{programDisplayName(item, favoriteProgramIds)}</option>
            ))}
          </select>
          <select name="rule_kind" defaultValue="linear">
            <option value="linear">一般比例</option>
            <option value="threshold_block">滿額加贈</option>
          </select>
          <input name="ratio_from" placeholder="送出數量，例如 60000" required />
          <input name="ratio_to" placeholder="實得數量，例如 20000" required />
          <input name="bonus_pct" placeholder="加贈百分比，沒有填 0" />
          <input name="min_transfer" placeholder="最低轉出點數，可留空" />
          <input name="block_size" placeholder="每滿多少送點，例如 60000" />
          <input name="block_bonus_points" placeholder="滿額額外送點，例如 5000" />
          <input name="valid_until" type="date" />
          <input name="source_url" placeholder="查證連結" />
          <button
            className="button button-primary"
            type="button"
            onClick={() => submit(() => createTransferRule({
              from_program_id: program.id,
              to_program_id: Number(field(form, "to_program_id")),
              ratio_from: field(form, "ratio_from"),
              ratio_to: field(form, "ratio_to"),
              bonus_pct: field(form, "bonus_pct") || "0",
              min_transfer: field(form, "min_transfer") || undefined,
              valid_from: today(),
              valid_until: field(form, "valid_until") || undefined,
              transfer_days_note: "手動新增",
              rule_kind: field(form, "rule_kind"),
              block_size: field(form, "block_size") || undefined,
              block_bonus_points: field(form, "block_bonus_points") || undefined,
              source_url: field(form, "source_url") || undefined,
            }), "兌換規則已新增。")}
          >
            加入規則
          </button>
        </>
      )}
    </FormPanel>
  );
}

function AiParsePanel({
  sourceProgram,
  programs,
  favoriteProgramIds,
  submit,
}: {
  sourceProgram: Program;
  programs: Program[];
  favoriteProgramIds: number[];
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<WalletAiParsedRule | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const target = preview?.to_program_name ? findProgramByAliases(programs, [preview.to_program_name]) : null;

  async function parse() {
    const response = await parseWalletRuleWithAi({ source_program_name: sourceProgram.name, pasted_text: text });
    setPreview(response.preview);
    setMessage(response.message);
  }

  return (
    <section className="form-panel">
      <h2>AI 解析</h2>
      <p className="subtle">貼上促銷文字後只會產生待確認預覽；按確認才會入庫，且不會自動抓網頁。</p>
      <textarea className={styles.textArea} value={text} onChange={(event) => setText(event.target.value)} placeholder="貼上活動公告或促銷文字" />
      <button className="button" type="button" onClick={() => void parse()} disabled={!text.trim()}>
        解析文字
      </button>
      {message ? <p className="subtle">{message}</p> : null}
      {preview ? (
        <div className={styles.previewCard}>
          <strong>待確認：{programDisplayName(sourceProgram, favoriteProgramIds)} → {target ? programDisplayName(target, favoriteProgramIds) : preview.to_program_name || "未辨識目的地"}</strong>
          <p>比例 {preview.ratio_from || "?"} : {preview.ratio_to || "?"}，加贈 {preview.bonus_pct || "0"}%</p>
          <p>{humanThreshold(preview.rule_kind || "linear", preview.block_size, preview.block_bonus_points)}</p>
          <button
            className="button button-primary"
            type="button"
            disabled={!target || !preview.ratio_from || !preview.ratio_to}
            onClick={() => submit(() => createTransferRule({
              from_program_id: sourceProgram.id,
              to_program_id: Number(target?.id),
              ratio_from: preview.ratio_from || "0",
              ratio_to: preview.ratio_to || "0",
              bonus_pct: preview.bonus_pct || "0",
              min_transfer: preview.min_transfer || undefined,
              valid_from: today(),
              valid_until: preview.valid_until || undefined,
              transfer_days_note: "AI解析-已人工確認",
              rule_kind: preview.rule_kind || "linear",
              block_size: preview.block_size || undefined,
              block_bonus_points: preview.block_bonus_points || undefined,
              source_url: preview.source_url || undefined,
            }), "AI 解析規則已人工確認並加入。")}
          >
            確認加入
          </button>
          {!target ? <p className="pending-text">目的地計畫尚未存在，請先到「我的點數」新增計畫。</p> : null}
        </div>
      ) : null}
    </section>
  );
}

function OtherSourcesPanel({
  programs,
  sourcePrograms,
  pinnedSources,
  favoriteProgramIds,
  setPinnedSources,
}: {
  programs: Program[];
  sourcePrograms: Program[];
  pinnedSources: number[];
  favoriteProgramIds: number[];
  setPinnedSources: (value: number[] | ((current: number[]) => number[])) => void;
}) {
  const sourceIds = new Set(sourcePrograms.map((program) => program.id));
  const candidates = programs.filter((program) => !primaryTabForProgram(program) && sourceIds.has(program.id));
  return (
    <section className="panel">
      <h2>其他來源</h2>
      <p className="subtle">這裡收納萬里通、萬豪、吉祥以外的來源計畫；可釘選保存偏好。</p>
      <div className={styles.sourceGrid}>
        {candidates.map((program) => (
          <article className={styles.sourceCard} key={program.id}>
            <h3>{programDisplayName(program, favoriteProgramIds)}</h3>
            <p>{KIND_LABELS.programKind[program.kind] || program.kind}</p>
            <button
              className="button"
              type="button"
              onClick={() => setPinnedSources((current) => (current.includes(program.id) ? current.filter((id) => id !== program.id) : [...current, program.id]))}
            >
              {pinnedSources.includes(program.id) ? "取消釘選" : "釘選來源"}
            </button>
          </article>
        ))}
        {candidates.length === 0 ? <p className="pending-text">目前沒有其他來源計畫。</p> : null}
      </div>
    </section>
  );
}

function MyPointsPanel({
  sortedPrograms,
  favoriteProgramIds,
  accounts,
  hotelVouchers,
  portfolio,
  prefs,
  updatePrefs,
  submit,
}: {
  sortedPrograms: Program[];
  favoriteProgramIds: number[];
  accounts: Account[];
  hotelVouchers: HotelVoucher[];
  portfolio: Portfolio | null;
  prefs: Preferences;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  return (
    <>
      <section className="panel">
        <h2>我的點數</h2>
        <p className="subtle">新增交易入口放在每個帳戶旁邊；帳號只存遮罩備註，不存任何登入資訊。</p>
        <div className={styles.accountList}>
          {(portfolio?.accounts || []).map((row) => {
            const account = accounts.find((item) => item.id === Number(row.account_id));
            if (!account) return null;
            return (
              <AccountRow
                key={account.id}
                account={account}
                row={row}
                favoriteProgramIds={favoriteProgramIds}
                prefs={prefs}
                updatePrefs={updatePrefs}
                submit={submit}
              />
            );
          })}
          {(portfolio?.accounts || []).length === 0 ? <p className="pending-text">目前沒有帳戶。</p> : null}
        </div>
      </section>

      <div className={styles.grid}>
        <ProgramForm submit={submit} />
        <AccountForm
          programs={sortedPrograms}
          favoriteProgramIds={favoriteProgramIds}
          selectedProgramId={prefs.programId}
          updatePrefs={updatePrefs}
          submit={submit}
        />
      </div>

      <section className="panel">
        <h2>免房券</h2>
        <p className="subtle">記錄飯店 FNC 免房券；90 天內到期會在儀表板以紅色提示。</p>
        <div className={styles.accountList}>
          {hotelVouchers.map((voucher) => (
            <HotelVoucherRow key={voucher.id} voucher={voucher} submit={submit} />
          ))}
          {hotelVouchers.length === 0 ? <p className="pending-text">目前沒有免房券。</p> : null}
        </div>
      </section>

      <HotelVoucherForm
        programs={sortedPrograms.filter((program) => program.kind === "hotel")}
        favoriteProgramIds={favoriteProgramIds}
        selectedProgramId={prefs.programId}
        updatePrefs={updatePrefs}
        submit={submit}
      />
    </>
  );
}

function HotelVoucherRow({
  voucher,
  submit,
}: {
  voucher: HotelVoucher;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  const daysLeft = daysUntil(voucher.expires_at);
  const isUrgent = voucher.status === "active" && daysLeft !== null && daysLeft <= 90;
  return (
    <article className={`${styles.accountRow} ${isUrgent ? styles.urgentVoucher : ""}`}>
      <div>
        <strong>{OWNER_LABELS[voucher.owner] || voucher.owner} · {voucher.program_name} 免房券</strong>
        <p className="subtle">
          面額 {formatNumber(voucher.face_value_points)} 點，到期 {voucher.expires_at}
          {daysLeft !== null ? `，剩 ${daysLeft} 天` : ""}，狀態 {voucherStatusLabel(voucher.status)}
        </p>
        {voucher.acquired_note ? <p className="subtle">{voucher.acquired_note}</p> : null}
      </div>
      {voucher.status === "active" ? (
        <button
          className="button"
          type="button"
          onClick={() => submit(() => updateHotelVoucherStatus(voucher.id, { status: "used", used_note: "使用者於錢包頁標記已使用" }), "免房券已標記使用。")}
        >
          標記已使用
        </button>
      ) : null}
    </article>
  );
}

function HotelVoucherForm({
  programs,
  favoriteProgramIds,
  selectedProgramId,
  updatePrefs,
  submit,
}: {
  programs: Program[];
  favoriteProgramIds: number[];
  selectedProgramId: string;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  return (
    <FormPanel title="新增免房券" description="使用既有飯店計畫下拉；缺少飯店計畫時，請先用新增計畫建立。">
      {(form) => (
        <>
          <select name="owner" defaultValue="kent">
            <option value="kent">凱章</option>
            <option value="wife">老婆</option>
          </select>
          <ProgramSelect
            programs={programs}
            favoriteProgramIds={favoriteProgramIds}
            value={selectedProgramId}
            onChange={(value) => updatePrefs({ programId: value })}
          />
          <input name="face_value_points" placeholder="面額，例如 50000" defaultValue="50000" required />
          <input name="expires_at" type="date" required />
          <input name="acquired_note" placeholder="取得備註，例如 信用卡年度免房券" />
          <button
            className="button button-primary"
            type="button"
            disabled={programs.length === 0}
            onClick={() => submit(() => createHotelVoucher({
              owner: field(form, "owner"),
              program_id: Number(field(form, "program_id")),
              face_value_points: field(form, "face_value_points"),
              expires_at: field(form, "expires_at"),
              acquired_note: field(form, "acquired_note") || null,
            }), "免房券已新增。")}
          >
            新增免房券
          </button>
        </>
      )}
    </FormPanel>
  );
}

function AccountRow({
  account,
  row,
  favoriteProgramIds,
  prefs,
  updatePrefs,
  submit,
}: {
  account: Account;
  row: Record<string, string | number | null>;
  favoriteProgramIds: number[];
  prefs: Preferences;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <article className={styles.accountRow}>
      <div>
        <strong>{OWNER_LABELS[account.owner] || account.owner} · {favoriteLabelFromName(String(row.program_name), favoriteProgramIds, account.program_id)}</strong>
        <p className="subtle">餘額 {formatNumber(row.balance)}，每點成本 {costPerPoint(row.avg_cost_per_point_twd)}，到期 {String(row.expires_at || "未設定")}</p>
      </div>
      <button className="button" type="button" onClick={() => setOpen((value) => !value)}>
        新增交易
      </button>
      {open ? (
        <FormPanel title="帳本記錄" description="這筆會寫入不可修改帳本；成本批次只在勾選時建立。">
          {(form) => (
            <>
              <select name="kind" value={prefs.kind} onChange={(event) => updatePrefs({ kind: event.target.value })}>
                {LEDGER_KIND_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
              <input name="quantity" placeholder="點數數量；使用或到期請輸入負數" required />
              <input name="occurred_at" type="date" defaultValue={today()} required />
              <input name="cost_total" placeholder="總成本，可留空" />
              <select name="cost_currency" value={prefs.currency} onChange={(event) => updatePrefs({ currency: event.target.value })}>
                {CURRENCY_OPTIONS.map((currency) => <option key={currency} value={currency}>{currency}</option>)}
              </select>
              <label className={styles.checkboxLine}>
                <input name="create_lot" type="checkbox" /> 這筆建立成本批次
              </label>
              <input name="note" placeholder="備註" />
              <button
                className="button button-primary"
                type="button"
                onClick={() => submit(() => createLedger({
                  account_id: account.id,
                  kind: field(form, "kind"),
                  quantity: field(form, "quantity"),
                  occurred_at: field(form, "occurred_at"),
                  cost_total: field(form, "cost_total") || null,
                  cost_currency: field(form, "cost_currency") || null,
                  note: field(form, "note"),
                  create_lot: field(form, "create_lot") === "on",
                }), "帳本記錄已新增。")}
              >
                儲存交易
              </button>
            </>
          )}
        </FormPanel>
      ) : null}
    </article>
  );
}

function ProgramForm({
  submit,
}: {
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  return (
    <FormPanel title="新增計畫" description="如果資料庫還沒有這個航空、飯店或銀行點數計畫，先在這裡建立。">
      {(form) => (
        <>
          <input name="name" placeholder="例如 Qatar Avios" required />
          <select name="kind" defaultValue="airline" required>
            {PROGRAM_KIND_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <input name="expiry_rule_note" placeholder="到期規則備註" />
          <button
            className="button button-primary"
            type="button"
            onClick={() => submit(() => createProgram({
              name: field(form, "name"),
              kind: field(form, "kind"),
              expiry_rule_note: field(form, "expiry_rule_note"),
            }), "計畫已新增。")}
          >
            新增計畫
          </button>
        </>
      )}
    </FormPanel>
  );
}

function AccountForm({
  programs,
  favoriteProgramIds,
  selectedProgramId,
  updatePrefs,
  submit,
}: {
  programs: Program[];
  favoriteProgramIds: number[];
  selectedProgramId: string;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  return (
    <FormPanel title="新增帳戶" description="新增凱章或老婆名下的點數帳戶。">
      {(form) => (
        <>
          <select name="owner" defaultValue="kent">
            <option value="kent">凱章</option>
            <option value="wife">老婆</option>
          </select>
          <ProgramSelect
            programs={programs}
            favoriteProgramIds={favoriteProgramIds}
            value={selectedProgramId}
            onChange={(value) => updatePrefs({ programId: value })}
          />
          <input name="account_ref" placeholder="帳號末四碼或備註，不填也可以" />
          <input name="notes" placeholder="帳戶備註" />
          <button
            className="button button-primary"
            type="button"
            onClick={() => submit(() => createAccount({
              owner: field(form, "owner"),
              program_id: Number(field(form, "program_id")),
              account_ref: field(form, "account_ref"),
              notes: field(form, "notes"),
            }), "帳戶已新增。")}
          >
            新增帳戶
          </button>
        </>
      )}
    </FormPanel>
  );
}

function FormPanel({ title, description, children }: { title: string; description: string; children: (form: HTMLFormElement) => React.ReactNode }) {
  const [form, setForm] = useState<HTMLFormElement | null>(null);
  return (
    <form
      ref={(node) => {
        if (node !== form) setForm(node);
      }}
      className="form-panel"
      onSubmit={(event: FormEvent<HTMLFormElement>) => event.preventDefault()}
    >
      <h2>{title}</h2>
      <p className="subtle">{description}</p>
      <div className={styles.formGrid}>{form ? children(form) : null}</div>
    </form>
  );
}

function ProgramSelect({
  programs,
  favoriteProgramIds,
  value,
  onChange,
  name = "program_id",
}: {
  programs: Program[];
  favoriteProgramIds: number[];
  value?: string;
  onChange?: (value: string) => void;
  name?: string;
}) {
  const selectedValue = String(programs.find((program) => String(program.id) === value)?.id || programs[0]?.id || "");
  return (
    <select name={name} value={selectedValue} onChange={(event) => onChange?.(event.target.value)} required>
      <option value="">選擇計畫</option>
      {programs.map((program) => <option key={program.id} value={program.id}>{programDisplayName(program, favoriteProgramIds)}</option>)}
    </select>
  );
}

function Table({ columns, rows }: { columns: string[]; rows: string[][] }) {
  if (rows.length === 0) return <p className="pending-text">目前沒有資料。</p>;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>{row.map((cell, cellIndex) => <td key={`${index}-${cellIndex}`}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function editableRule(rule: TransferRule): EditableRule {
  return {
    from_program_id: String(rule.from_program_id),
    to_program_id: String(rule.to_program_id),
    ratio_from: rule.ratio_from,
    ratio_to: rule.ratio_to,
    bonus_pct: rule.bonus_pct,
    min_transfer: rule.min_transfer || "",
    valid_from: rule.valid_from,
    valid_until: rule.valid_until || "",
    transfer_days_note: rule.transfer_days_note || "",
    rule_kind: rule.rule_kind || "linear",
    block_size: rule.block_size || "",
    block_bonus_points: rule.block_bonus_points || "",
    source_url: rule.source_url || "",
  };
}

function transferRulePayload(draft: EditableRule) {
  return {
    from_program_id: Number(draft.from_program_id),
    to_program_id: Number(draft.to_program_id),
    ratio_from: draft.ratio_from,
    ratio_to: draft.ratio_to,
    bonus_pct: draft.bonus_pct || "0",
    min_transfer: draft.min_transfer || undefined,
    valid_from: draft.valid_from || today(),
    valid_until: draft.valid_until || undefined,
    transfer_days_note: draft.transfer_days_note,
    rule_kind: draft.rule_kind || "linear",
    block_size: draft.block_size || undefined,
    block_bonus_points: draft.block_bonus_points || undefined,
    source_url: draft.source_url || undefined,
  };
}

function calculateRequiredSourcePoints(rule: TransferRule, targetPoints: number): { requiredSourcePoints: number; receivedPoints: number } {
  if (!targetPoints || targetPoints <= 0) return { requiredSourcePoints: 0, receivedPoints: 0 };
  const ratioFrom = Number(rule.ratio_from || 0);
  const ratioTo = Number(rule.ratio_to || 0);
  if (!ratioFrom || !ratioTo) return { requiredSourcePoints: 0, receivedPoints: 0 };
  let source = Math.ceil((targetPoints / ratioTo) * ratioFrom);
  const minTransfer = Number(rule.min_transfer || 0);
  if (minTransfer > source) source = minTransfer;
  const step = ratioFrom > 0 ? ratioFrom : 1;
  source = Math.ceil(source / step) * step;
  let received = pointsReceived(rule, source);
  let guard = 0;
  while (received < targetPoints && guard < 10000) {
    source += step;
    received = pointsReceived(rule, source);
    guard += 1;
  }
  return { requiredSourcePoints: source, receivedPoints: received };
}

function pointsReceived(rule: TransferRule, sourcePoints: number): number {
  const ratioFrom = Number(rule.ratio_from || 0);
  const ratioTo = Number(rule.ratio_to || 0);
  if (!ratioFrom || !ratioTo) return 0;
  const base = Math.floor(sourcePoints / ratioFrom) * ratioTo;
  const bonus = Math.floor(base * (Number(rule.bonus_pct || 0) / 100));
  if (rule.rule_kind === "threshold_block") {
    const blockSize = Number(rule.block_size || 0);
    const blockBonus = Number(rule.block_bonus_points || 0);
    return base + bonus + (blockSize && blockBonus ? Math.floor(sourcePoints / blockSize) * blockBonus : 0);
  }
  return base + bonus;
}

function ruleRatioText(rule: TransferRule): string {
  return `${formatNumber(rule.ratio_from)}:${formatNumber(rule.ratio_to)}${Number(rule.bonus_pct || 0) > 0 ? ` +${formatNumber(rule.bonus_pct)}%` : ""}`;
}

function humanThreshold(kind: string, blockSize?: string | null, blockBonus?: string | null): string {
  if (kind !== "threshold_block") return "一般比例";
  if (!blockSize || !blockBonus) return "滿額加贈，門檻未完整";
  return `每滿 ${formatNumber(blockSize)} 送 ${formatNumber(blockBonus)} 點`;
}

function ownerBalances(portfolio: Portfolio | null, programId: number): { kent: number; wife: number } {
  const result = { kent: 0, wife: 0 };
  for (const row of portfolio?.accounts || []) {
    if (Number(row.program_id) !== programId) continue;
    if (row.owner === "kent") result.kent += Number(row.balance || 0);
    if (row.owner === "wife") result.wife += Number(row.balance || 0);
  }
  return result;
}

function sourceAvgCost(portfolio: Portfolio | null, programId: number): string {
  const costs = (portfolio?.accounts || [])
    .filter((row) => Number(row.program_id) === programId && row.avg_cost_per_point_twd)
    .map((row) => Number(row.avg_cost_per_point_twd));
  if (costs.length === 0) return "";
  return String(costs.reduce((sum, value) => sum + value, 0) / costs.length);
}

function primaryTabForProgram(program: Program): WalletTab | null {
  for (const item of PRIMARY_SOURCE_TABS) {
    if (item.aliases.some((alias) => program.name.toLowerCase().includes(alias.toLowerCase()))) return item.tab;
  }
  return null;
}

function sortRulesByTargetProgram(rules: TransferRule[], sortedPrograms: Program[]): TransferRule[] {
  const programOrder = new Map(sortedPrograms.map((program, index) => [program.id, index]));
  return [...rules].sort((left, right) => {
    const leftRank = programOrder.get(left.to_program_id) ?? 9999;
    const rightRank = programOrder.get(right.to_program_id) ?? 9999;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return left.id - right.id;
  });
}

function favoriteLabelFromName(name: string, favoriteProgramIds: number[], programId: number): string {
  return `${favoriteProgramIds.includes(programId) ? "⭐ " : ""}${name}`;
}

function field(form: HTMLFormElement, name: string): string {
  const value = new FormData(form).get(name);
  return typeof value === "string" ? value.trim() : "";
}

function formatMoney(value: unknown): string {
  const numberValue = Number(value || 0);
  return `NT$${numberValue.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}`;
}

function costPerPoint(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未設定";
  return `NT$${Number(value).toLocaleString("zh-TW", { minimumFractionDigits: 3, maximumFractionDigits: 3 })}/點`;
}

function daysUntil(value: string): number | null {
  if (!value) return null;
  const todayDate = new Date(today());
  const target = new Date(value);
  if (Number.isNaN(target.getTime())) return null;
  return Math.ceil((target.getTime() - todayDate.getTime()) / 86400000);
}

function voucherStatusLabel(status: string): string {
  if (status === "active") return "可用";
  if (status === "used") return "已使用";
  if (status === "expired") return "已過期";
  return status;
}

function formatNumber(value: unknown): string {
  return Number(value || 0).toLocaleString("zh-TW", { maximumFractionDigits: 2 });
}

function formatInteger(value: unknown): string {
  return Math.round(Number(value || 0)).toLocaleString("zh-TW", { maximumFractionDigits: 0 });
}

function integerInput(value: string): string {
  if (value === "") return "";
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? String(Math.round(numberValue)) : value.replace(/[^0-9-]/g, "");
}

function programInitial(name: string): string {
  const normalized = name.replace(/^⭐\s*/, "").trim();
  return normalized.slice(0, 1).toUpperCase() || "P";
}

function isWanlitong(program: Program): boolean {
  return ["萬里通", "平安萬里通", "wanlitong"].some((alias) => program.name.toLowerCase().includes(alias.toLowerCase()));
}

function latestFxRate(rates: FxRate[], currency: string): FxRate | null {
  return rates.find((rate) => rate.currency.toUpperCase() === currency.toUpperCase()) || null;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}
