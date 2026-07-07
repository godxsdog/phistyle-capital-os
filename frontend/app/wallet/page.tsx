"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  Account,
  Program,
  PurchaseOffer,
  TransferRule,
  createAccount,
  createLedger,
  createProgram,
  createPurchaseOffer,
  createTransferRule,
  getPortfolio,
  listAccounts,
  listPrograms,
  listPurchaseOffers,
  listTransferRules,
  refreshFxRates,
  Portfolio,
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
import styles from "./WalletPage.module.css";

const PREF_KEY = "phistyle.wallet.preferences";

type Preferences = {
  tab: WalletTab;
  owner: "kent" | "wife";
  programId: string;
  kind: string;
  currency: string;
};

const DEFAULT_PREFS: Preferences = {
  tab: "overview",
  owner: "kent",
  programId: "",
  kind: "adjustment",
  currency: "TWD",
};

export default function WalletPage() {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [rules, setRules] = useState<TransferRule[]>([]);
  const [offers, setOffers] = useState<PurchaseOffer[]>([]);
  const [portfolioAll, setPortfolioAll] = useState<Portfolio | null>(null);
  const [portfolioKent, setPortfolioKent] = useState<Portfolio | null>(null);
  const [portfolioWife, setPortfolioWife] = useState<Portfolio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [fromFilter, setFromFilter] = useState("");
  const [toFilter, setToFilter] = useState("");

  useEffect(() => {
    const stored = window.localStorage.getItem(PREF_KEY);
    if (!stored) return;
    try {
      setPrefs({ ...DEFAULT_PREFS, ...(JSON.parse(stored) as Partial<Preferences>) });
    } catch {
      window.localStorage.removeItem(PREF_KEY);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
  }, [prefs]);

  useEffect(() => {
    void loadWallet();
  }, []);

  const activeOwner = prefs.tab === "wife" ? "wife" : "kent";
  const activePortfolio = activeOwner === "wife" ? portfolioWife : portfolioKent;
  const ownerAccounts = useMemo(
    () => accounts.filter((account) => account.owner === activeOwner),
    [accounts, activeOwner],
  );
  async function loadWallet() {
    try {
      const [
        nextPrograms,
        nextAccounts,
        nextRules,
        nextOffers,
        nextPortfolioAll,
        nextPortfolioKent,
        nextPortfolioWife,
      ] = await Promise.all([
        listPrograms(),
        listAccounts(),
        listTransferRules(),
        listPurchaseOffers(),
        getPortfolio(),
        getPortfolio("kent"),
        getPortfolio("wife"),
      ]);
      setPrograms(nextPrograms);
      setAccounts(nextAccounts);
      setRules(nextRules);
      setOffers(nextOffers);
      setPortfolioAll(nextPortfolioAll);
      setPortfolioKent(nextPortfolioKent);
      setPortfolioWife(nextPortfolioWife);
      setError(null);
    } catch {
      setError("資料載入失敗，請稍後再試。");
    }
  }

  async function submit(action: () => Promise<unknown>, message: string) {
    try {
      await action();
      setStatus(message);
      await loadWallet();
    } catch {
      setError("儲存失敗，請確認欄位後再試。");
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
            <h1>點數與哩程帳本</h1>
            <p>用帳本記錄兩個人的點數、真實成本、到期風險、轉點規則與買分價格。</p>
          </div>
          <button className="button" type="button" onClick={() => submit(refreshFxRates, "匯率已更新；若外部服務失敗則使用備用匯率。")}>
            更新匯率
          </button>
          <Link className="button button-primary" href="/wallet/awards">
            兌換成本
          </Link>
        </section>

        <div className={styles.tabs} role="tablist" aria-label="點數錢包功能">
          {(Object.keys(TAB_LABELS) as WalletTab[]).map((tab) => (
            <button
              key={tab}
              className={`button ${prefs.tab === tab ? "button-primary" : ""}`}
              type="button"
              onClick={() => updatePrefs({ tab, owner: tab === "wife" ? "wife" : tab === "kent" ? "kent" : prefs.owner })}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>

        {error ? <div className="notice notice-error">{error}</div> : null}
        {status ? <p className="subtle">{status}</p> : null}

        {prefs.tab === "overview" ? (
          <OverviewPanel programs={programs} portfolio={portfolioAll} kent={portfolioKent} wife={portfolioWife} />
        ) : null}

        {prefs.tab === "kent" || prefs.tab === "wife" ? (
          <OwnerPanel
            owner={activeOwner}
            programs={programs}
            accounts={ownerAccounts}
            portfolio={activePortfolio}
            prefs={prefs}
            updatePrefs={updatePrefs}
            submit={submit}
          />
        ) : null}

        {prefs.tab === "transferRules" ? (
          <TransferRulesPanel
            programs={programs}
            rules={rules}
            fromFilter={fromFilter}
            toFilter={toFilter}
            setFromFilter={setFromFilter}
            setToFilter={setToFilter}
            prefs={prefs}
            updatePrefs={updatePrefs}
            submit={submit}
          />
        ) : null}

        {prefs.tab === "purchaseOffers" ? (
          <PurchaseOffersPanel programs={programs} offers={offers} prefs={prefs} updatePrefs={updatePrefs} submit={submit} />
        ) : null}
      </div>
    </main>
  );
}

function OverviewPanel({
  programs,
  portfolio,
  kent,
  wife,
}: {
  programs: Program[];
  portfolio: Portfolio | null;
  kent: Portfolio | null;
  wife: Portfolio | null;
}) {
  return (
    <>
      <section className="panel">
        <h2>總覽</h2>
        <p className="subtle">這裡看兩個人合計持有多少點、真實成本是多少，以及 90 天內會不會到期。</p>
        <div className="data-grid">
          <div>
            <dt>兩人合計真實成本</dt>
            <dd>{formatMoney(portfolio?.total_real_cost_basis_twd)}</dd>
          </div>
          <div>
            <dt>凱章真實成本</dt>
            <dd>{formatMoney(kent?.total_real_cost_basis_twd)}</dd>
          </div>
          <div>
            <dt>老婆真實成本</dt>
            <dd>{formatMoney(wife?.total_real_cost_basis_twd)}</dd>
          </div>
          <div>
            <dt>90 天內到期</dt>
            <dd>{portfolio?.expiring_soon.length ?? 0} 筆</dd>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>各計畫餘額</h2>
        <Table
          columns={["持有人", "計畫", "餘額", "剩餘成本批次", "真實成本", "每點成本", "買分估值", "到期日"]}
          rows={(portfolio?.accounts || []).map((row) => accountSummaryRow(row))}
        />
      </section>

      <section className="panel">
        <h2>到期警示</h2>
        <Table
          columns={["持有人", "計畫", "餘額", "到期日"]}
          rows={(portfolio?.expiring_soon || []).map((row) => [
            ownerLabel(String(row.owner)),
            String(row.program_name),
            formatNumber(row.balance),
            String(row.expires_at || "未設定"),
          ])}
        />
      </section>

      <section className="panel">
        <h2>計畫清單</h2>
        <Table
          columns={["計畫", "類型", "到期規則"]}
          rows={programs.map((program) => [
            program.name,
            KIND_LABELS.programKind[program.kind] || program.kind,
            program.expiry_rule_note || "未設定",
          ])}
        />
      </section>
    </>
  );
}

function OwnerPanel({
  owner,
  programs,
  accounts,
  portfolio,
  prefs,
  updatePrefs,
  submit,
}: {
  owner: "kent" | "wife";
  programs: Program[];
  accounts: Account[];
  portfolio: Portfolio | null;
  prefs: Preferences;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  return (
    <>
      <section className="panel">
        <h2>{OWNER_LABELS[owner]}帳戶</h2>
        <p className="subtle">這裡只看 {OWNER_LABELS[owner]} 的點數餘額、真實成本與到期日。</p>
        <Table
          columns={["計畫", "餘額", "剩餘成本批次", "真實成本", "每點成本", "買分估值", "到期日"]}
          rows={(portfolio?.accounts || []).map((row) => accountSummaryRow(row).slice(1))}
        />
      </section>

      <div className={styles.grid}>
        <ProgramForm prefs={prefs} updatePrefs={updatePrefs} submit={submit} />
        <AccountForm owner={owner} programs={programs} submit={submit} />
        <LedgerForm owner={owner} accounts={accounts} programs={programs} prefs={prefs} updatePrefs={updatePrefs} submit={submit} />
      </div>
    </>
  );
}

function ProgramForm({
  prefs,
  updatePrefs,
  submit,
}: {
  prefs: Preferences;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  return (
    <FormPanel title="新增計畫" description="如果資料庫還沒有這個航空、飯店或銀行點數計畫，先在這裡建立。">
      {(form) => (
        <>
          <input name="name" placeholder="例如 Qatar Avios" required />
          <select name="kind" defaultValue="airline" required>
            {PROGRAM_KIND_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
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
  owner,
  programs,
  submit,
}: {
  owner: "kent" | "wife";
  programs: Program[];
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  return (
    <FormPanel title={`新增${OWNER_LABELS[owner]}帳戶`} description="在這裡把某個點數計畫掛到持有人名下；帳號只存遮罩備註，不存登入資訊。">
      {(form) => (
        <>
          <ProgramSelect programs={programs} />
          <input name="account_ref" placeholder="帳號末四碼或備註，不填也可以" />
          <input name="notes" placeholder="帳戶備註" />
          <button
            className="button button-primary"
            type="button"
            onClick={() => submit(() => createAccount({
              owner,
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

function LedgerForm({
  owner,
  accounts,
  programs,
  prefs,
  updatePrefs,
  submit,
}: {
  owner: "kent" | "wife";
  accounts: Account[];
  programs: Program[];
  prefs: Preferences;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  const selectedProgramId = prefs.programId || String(accounts[0]?.program_id || "");
  const filteredAccounts = accounts.filter((account) => !selectedProgramId || String(account.program_id) === selectedProgramId);

  return (
    <FormPanel title={`${OWNER_LABELS[owner]}帳本記錄`} description="在這裡記錄點數的取得或使用，每一筆都會留下不可修改的帳本記錄。">
      {(form) => (
        <>
          <ProgramSelect
            programs={programsForAccounts(programs, accounts)}
            value={selectedProgramId}
            onChange={(value) => updatePrefs({ programId: value })}
          />
          <select name="account_id" required>
            <option value="">選擇帳戶</option>
            {filteredAccounts.map((account) => (
              <option key={account.id} value={account.id}>{OWNER_LABELS[owner]} · {programName(programs, account.program_id)}</option>
            ))}
          </select>
          <select name="kind" value={prefs.kind} onChange={(event) => updatePrefs({ kind: event.target.value })} required>
            {LEDGER_KIND_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <input name="quantity" placeholder="點數數量；使用或到期請輸入負數" required />
          <input name="occurred_at" type="date" defaultValue={today()} required />
          <input name="cost_total" placeholder="總成本，可留空" />
          <select name="cost_currency" value={prefs.currency} onChange={(event) => updatePrefs({ currency: event.target.value })}>
            {CURRENCY_OPTIONS.map((currency) => (
              <option key={currency} value={currency}>{currency}</option>
            ))}
          </select>
          <label className={styles.checkboxLine}>
            <input name="create_lot" type="checkbox" /> 這筆建立成本批次
          </label>
          <input name="note" placeholder="備註" />
          <button
            className="button button-primary"
            type="button"
            onClick={() => submit(() => createLedger({
              account_id: Number(field(form, "account_id")),
              kind: field(form, "kind"),
              quantity: field(form, "quantity"),
              occurred_at: field(form, "occurred_at"),
              cost_total: field(form, "cost_total") || null,
              cost_currency: field(form, "cost_currency") || null,
              note: field(form, "note"),
              create_lot: field(form, "create_lot") === "on",
            }), "帳本記錄已新增。")}
          >
            新增帳本
          </button>
        </>
      )}
    </FormPanel>
  );
}

function TransferRulesPanel({
  programs,
  rules,
  fromFilter,
  toFilter,
  setFromFilter,
  setToFilter,
  prefs,
  updatePrefs,
  submit,
}: {
  programs: Program[];
  rules: TransferRule[];
  fromFilter: string;
  toFilter: string;
  setFromFilter: (value: string) => void;
  setToFilter: (value: string) => void;
  prefs: Preferences;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  const fromProgramIds = Array.from(new Set(rules.map((rule) => rule.from_program_id)));
  const activeFromFilter = fromFilter || String(fromProgramIds[0] || "");
  const visibleRules = rules.filter((rule) => {
    if (activeFromFilter && String(rule.from_program_id) !== activeFromFilter) return false;
    if (toFilter && String(rule.to_program_id) !== toFilter) return false;
    return true;
  });

  return (
    <>
      <section className="panel">
        <h2>轉點規則</h2>
        <p className="subtle">這裡用人話顯示轉點比例、加贈與有效期，比例統一寫成「送出 → 實得」。</p>
        <div className={styles.tabs} role="tablist" aria-label="來源計畫">
          {fromProgramIds.length === 0 ? (
            <span className="pending-text">目前沒有來源計畫。</span>
          ) : (
            fromProgramIds.map((programId) => (
              <button
                className={`button ${activeFromFilter === String(programId) ? "button-primary" : ""}`}
                key={programId}
                type="button"
                onClick={() => setFromFilter(String(programId))}
              >
                {programName(programs, programId)}
              </button>
            ))
          )}
        </div>
        <div className={styles.filterRow}>
          <ProgramSelect programs={programs} name="to_filter" value={toFilter} onChange={setToFilter} includeAll allLabel="全部目的地" />
        </div>
        <div className={styles.ruleList}>
          {visibleRules.length === 0 ? (
            <p className="pending-text">目前沒有符合條件的轉點規則。</p>
          ) : (
            visibleRules.map((rule) => (
              <div className={styles.ruleSentence} key={rule.id}>
                <span>{transferSentence(rule, programs)}</span>
                {rule.source_url ? (
                  <a href={rule.source_url} target="_blank" rel="noreferrer">查證</a>
                ) : null}
              </div>
            ))
          )}
        </div>
      </section>

      <FormPanel title="新增轉點規則" description="在這裡維護銀行點、飯店點、航空哩程之間的固定轉換規則。">
        {(form) => (
          <>
            <ProgramSelect programs={programs} name="from_program_id" value={prefs.programId} onChange={(value) => updatePrefs({ programId: value })} />
            <ProgramSelect programs={programs} name="to_program_id" />
            <select name="rule_kind" defaultValue="linear">
              <option value="linear">一般比例</option>
              <option value="threshold_block">滿額加贈</option>
            </select>
            <input name="ratio_from" placeholder="送出數量，例如 30000" required />
            <input name="ratio_to" placeholder="基礎實得，例如 10000" required />
            <input name="bonus_pct" placeholder="加贈百分比，例如 20" />
            <input name="min_transfer" placeholder="最低轉出點數，可留空" />
            <input name="block_size" placeholder="滿額門檻，例如 60000" />
            <input name="block_bonus_points" placeholder="滿額加贈點數，例如 5000" />
            <input name="valid_from" type="date" defaultValue={today()} required />
            <input name="valid_until" type="date" />
            <input name="transfer_days_note" placeholder="處理天數或備註" />
            <input name="source_url" placeholder="查證網址，可留空" />
            <button
              className="button button-primary"
              type="button"
              onClick={() => submit(() => createTransferRule({
                from_program_id: Number(field(form, "from_program_id")),
                to_program_id: Number(field(form, "to_program_id")),
                ratio_from: field(form, "ratio_from"),
                ratio_to: field(form, "ratio_to"),
                bonus_pct: field(form, "bonus_pct") || "0",
                min_transfer: field(form, "min_transfer") || undefined,
                valid_from: field(form, "valid_from"),
                valid_until: field(form, "valid_until") || undefined,
                transfer_days_note: field(form, "transfer_days_note"),
                rule_kind: field(form, "rule_kind"),
                block_size: field(form, "block_size") || undefined,
                block_bonus_points: field(form, "block_bonus_points") || undefined,
                source_url: field(form, "source_url") || undefined,
              }), "轉點規則已新增。")}
            >
              新增規則
            </button>
          </>
        )}
      </FormPanel>
    </>
  );
}

function PurchaseOffersPanel({
  programs,
  offers,
  prefs,
  updatePrefs,
  submit,
}: {
  programs: Program[];
  offers: PurchaseOffer[];
  prefs: Preferences;
  updatePrefs: (next: Partial<Preferences>) => void;
  submit: (action: () => Promise<unknown>, message: string) => Promise<void>;
}) {
  return (
    <>
      <section className="panel">
        <h2>買分價格</h2>
        <p className="subtle">這裡記錄官方、活動或手動查到的買分價格；每點成本會統一成新台幣格式比較。</p>
        <Table
          columns={["計畫", "類型", "原始價格", "加贈", "每點成本", "來源"]}
          rows={offers.map((offer) => [
            programName(programs, offer.program_id),
            KIND_LABELS.offerKind[offer.kind] || offer.kind,
            `${formatNumber(offer.base_price)} ${offer.currency}`,
            `${formatNumber(offer.bonus_pct)}%`,
            costPerPoint(offer.effective_cpp),
            offer.source_url ? `查證：${offer.source_url}` : offer.source_note || "未填寫",
          ])}
        />
      </section>

      <FormPanel title="新增買分價格" description="在這裡手動維護買分價格；TripPlus 仍是手動資料，不做爬蟲。">
        {(form) => (
          <>
            <ProgramSelect programs={programs} value={prefs.programId} onChange={(value) => updatePrefs({ programId: value })} />
            <select name="kind" defaultValue="official">
              <option value="official">官方</option>
              <option value="promo">活動</option>
              <option value="third_party">第三方手動</option>
            </select>
            <input name="base_price" placeholder="每點原始價格" required />
            <select name="currency" value={prefs.currency} onChange={(event) => updatePrefs({ currency: event.target.value })}>
              {CURRENCY_OPTIONS.map((currency) => (
                <option key={currency} value={currency}>{currency}</option>
              ))}
            </select>
            <input name="bonus_pct" placeholder="加贈百分比" />
            <input name="paid_amount" placeholder="實付金額，可留空" />
            <input name="fees" placeholder="手續費，可留空" />
            <input name="rebate" placeholder="回饋，可留空" />
            <input name="points_received" placeholder="實際入帳點數，可留空" />
            <input name="start_date" type="date" defaultValue={today()} required />
            <input name="end_date" type="date" />
            <input name="source_note" placeholder="來源備註" />
            <input name="source_url" placeholder="查證網址，可留空" />
            <button
              className="button button-primary"
              type="button"
              onClick={() => submit(() => createPurchaseOffer({
                program_id: Number(field(form, "program_id")),
                kind: field(form, "kind"),
                base_price: field(form, "base_price"),
                currency: field(form, "currency"),
                bonus_pct: field(form, "bonus_pct") || "0",
                start_date: field(form, "start_date"),
                end_date: field(form, "end_date") || undefined,
                source_note: field(form, "source_note"),
                paid_amount: field(form, "paid_amount") || undefined,
                fees: field(form, "fees") || undefined,
                rebate: field(form, "rebate") || undefined,
                points_received: field(form, "points_received") || undefined,
                source_url: field(form, "source_url") || undefined,
              }), "買分價格已新增。")}
            >
              新增價格
            </button>
          </>
        )}
      </FormPanel>
    </>
  );
}

function FormPanel({ title, description, children }: { title: string; description: string; children: (form: HTMLFormElement) => ReactNode }) {
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
  name = "program_id",
  value,
  onChange,
  includeAll = false,
  allLabel = "全部",
}: {
  programs: Program[];
  name?: string;
  value?: string;
  onChange?: (value: string) => void;
  includeAll?: boolean;
  allLabel?: string;
}) {
  return (
    <select name={name} value={value} onChange={(event) => onChange?.(event.target.value)} required={!includeAll}>
      {includeAll ? <option value="">{allLabel}</option> : <option value="">選擇計畫</option>}
      {programs.map((program) => (
        <option key={program.id} value={program.id}>{program.name}</option>
      ))}
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

function accountSummaryRow(row: Record<string, string | number | null>): string[] {
  return [
    ownerLabel(String(row.owner)),
    String(row.program_name),
    formatNumber(row.balance),
    formatNumber(row.remaining_lot_quantity),
    formatMoney(row.real_cost_basis_twd),
    costPerPoint(row.avg_cost_per_point_twd),
    row.market_value_twd ? formatMoney(row.market_value_twd) : "未設定",
    String(row.expires_at || "未設定"),
  ];
}

function transferSentence(rule: TransferRule, programs: Program[]): string {
  const fromName = programName(programs, rule.from_program_id);
  const toName = programName(programs, rule.to_program_id);
  const ratioFrom = Number(rule.ratio_from);
  const ratioTo = Number(rule.ratio_to);
  const sent = ratioFrom < 1000 ? ratioFrom * 10000 : ratioFrom;
  const base = ratioFrom > 0 ? (sent / ratioFrom) * ratioTo : 0;
  const bonus = Number(rule.bonus_pct || 0);
  if (rule.rule_kind === "threshold_block") {
    const blockSize = Number(rule.block_size || 0);
    const blockBonus = Number(rule.block_bonus_points || 0);
    const blockText = blockSize && blockBonus ? `每滿 ${formatNumber(blockSize)} 額外送 ${formatNumber(blockBonus)} 點,` : "";
    return `${fromName} → ${toName}:${formatNumber(sent)} → ${formatNumber(base)}(${formatNumber(ratioFrom)}:${formatNumber(ratioTo)},${blockText}有效至 ${rule.valid_until || "未設定"})`;
  }
  const received = Math.round(base * (1 + bonus / 100));
  const bonusText = bonus > 0 ? `,+${formatNumber(bonus)}% 加贈, 實得 ${formatNumber(received)}` : `,實得 ${formatNumber(received)}`;
  const until = rule.valid_until || "未設定";
  return `${fromName} → ${toName}:${formatNumber(sent)} → ${formatNumber(base)}(${formatNumber(ratioFrom / ratioTo)}:1${bonusText};有效至 ${until})`;
}

function programsForAccounts(programs: Program[], accounts: Account[]): Program[] {
  const accountProgramIds = new Set(accounts.map((account) => account.program_id));
  return programs.filter((program) => accountProgramIds.has(program.id));
}

function field(form: HTMLFormElement, name: string): string {
  const value = new FormData(form).get(name);
  return typeof value === "string" ? value.trim() : "";
}

function programName(programs: Program[], id: number): string {
  return programs.find((program) => program.id === id)?.name || `計畫 #${id}`;
}

function ownerLabel(value: string): string {
  return OWNER_LABELS[value] || value;
}

function formatMoney(value: unknown): string {
  const numberValue = Number(value || 0);
  return `NT$${numberValue.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}`;
}

function costPerPoint(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未設定";
  return `NT$${Number(value).toLocaleString("zh-TW", { minimumFractionDigits: 3, maximumFractionDigits: 3 })}/點`;
}

function formatNumber(value: unknown): string {
  return Number(value || 0).toLocaleString("zh-TW", { maximumFractionDigits: 2 });
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}
