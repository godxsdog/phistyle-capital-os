"use client";

import Link from "next/link";
import { FormEvent, ReactNode, useEffect, useState } from "react";
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
import styles from "./WalletPage.module.css";

export default function WalletPage() {
  const [owner, setOwner] = useState("kent");
  const [programs, setPrograms] = useState<Program[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [rules, setRules] = useState<TransferRule[]>([]);
  const [offers, setOffers] = useState<PurchaseOffer[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    void loadWallet(owner);
  }, [owner]);

  async function loadWallet(nextOwner = owner) {
    try {
      const [nextPrograms, nextAccounts, nextRules, nextOffers, nextPortfolio] = await Promise.all([
        listPrograms(),
        listAccounts(),
        listTransferRules(),
        listPurchaseOffers(),
        getPortfolio(nextOwner),
      ]);
      setPrograms(nextPrograms);
      setAccounts(nextAccounts);
      setRules(nextRules);
      setOffers(nextOffers);
      setPortfolio(nextPortfolio);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to load wallet.");
    }
  }

  async function submit(action: () => Promise<unknown>, message: string) {
    try {
      await action();
      setStatus(message);
      await loadWallet();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Request failed.");
    }
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>Point Wallet</span>
        </nav>
        <section className="page-header">
          <div>
            <div className="section-kicker">Point Wallet</div>
            <h1>Points & Miles Ledger</h1>
            <p>Track owner balances, true lot-level cost basis, expiry risk, transfer rules, and purchase offers.</p>
          </div>
          <button className="button" type="button" onClick={() => submit(refreshFxRates, "FX rates refreshed or fallback cached.")}>
            Refresh FX
          </button>
        </section>
        <div className={styles.ownerTabs}>
          {["kent", "wife"].map((nextOwner) => (
            <button
              key={nextOwner}
              className={`button ${owner === nextOwner ? "button-primary" : ""}`}
              type="button"
              onClick={() => setOwner(nextOwner)}
            >
              {nextOwner}
            </button>
          ))}
        </div>
        {error ? <div className="notice notice-error">{error}</div> : null}
        {status ? <p className="subtle">{status}</p> : null}
        <section className="panel">
          <h2>Portfolio</h2>
          <div className="data-grid">
            <div>
              <dt>Total Real Cost Basis</dt>
              <dd>{portfolio?.total_real_cost_basis_twd ?? "0"}</dd>
            </div>
            <div>
              <dt>Expiring ≤90 Days</dt>
              <dd>{portfolio?.expiring_soon.length ?? 0}</dd>
            </div>
          </div>
          <Table columns={["Program", "Balance", "Remaining Lots", "Real Cost", "Avg Cost", "Market Value", "Expires"]} rows={(portfolio?.accounts || []).map((row) => [
            String(row.program_name),
            String(row.balance),
            String(row.remaining_lot_quantity),
            String(row.real_cost_basis_twd),
            String(row.avg_cost_per_point_twd || "none"),
            String(row.market_value_twd || "none"),
            String(row.expires_at || "none"),
          ])} />
        </section>
        <div className={styles.grid}>
          <ProgramForm onSubmit={submit} />
          <AccountForm programs={programs} onSubmit={submit} />
          <LedgerForm accounts={accounts} programs={programs} onSubmit={submit} />
          <TransferRuleForm programs={programs} onSubmit={submit} />
          <PurchaseOfferForm programs={programs} onSubmit={submit} />
        </div>
        <section className="panel">
          <h2>Transfer Rules</h2>
          <Table columns={["From", "To", "Ratio", "Bonus", "Valid From", "Note"]} rows={rules.map((rule) => [
            programName(programs, rule.from_program_id),
            programName(programs, rule.to_program_id),
            `${rule.ratio_from}:${rule.ratio_to}`,
            `${rule.bonus_pct}%`,
            rule.valid_from,
            rule.transfer_days_note || "",
          ])} />
        </section>
        <section className="panel">
          <h2>Purchase Offers</h2>
          <Table columns={["Program", "Kind", "Base", "Bonus", "Effective CPP", "Source"]} rows={offers.map((offer) => [
            programName(programs, offer.program_id),
            offer.kind,
            `${offer.base_price} ${offer.currency}`,
            `${offer.bonus_pct}%`,
            offer.effective_cpp,
            offer.source_note || "",
          ])} />
        </section>
      </div>
    </main>
  );
}

function ProgramForm({ onSubmit }: FormProps) {
  return (
    <FormPanel title="Program" onSubmit={(form) => onSubmit(() => createProgram({
      name: field(form, "name"),
      kind: field(form, "kind"),
      expiry_rule_note: field(form, "expiry_rule_note"),
    }), "Program added.")}>
      <input name="name" placeholder="Program name" required />
      <input name="kind" placeholder="airline | hotel | bank | other" required />
      <input name="expiry_rule_note" placeholder="Expiry rule note" />
    </FormPanel>
  );
}

function AccountForm({ programs, onSubmit }: FormProps & { programs: Program[] }) {
  return (
    <FormPanel title="Account" onSubmit={(form) => onSubmit(() => createAccount({
      owner: field(form, "owner"),
      program_id: Number(field(form, "program_id")),
      account_ref: field(form, "account_ref"),
      notes: field(form, "notes"),
    }), "Account added.")}>
      <select name="owner" required>
        <option value="kent">kent</option>
        <option value="wife">wife</option>
      </select>
      <ProgramSelect programs={programs} />
      <input name="account_ref" placeholder="Masked account ref only" />
      <input name="notes" placeholder="Notes" />
    </FormPanel>
  );
}

function LedgerForm({ accounts, programs, onSubmit }: FormProps & { accounts: Account[]; programs: Program[] }) {
  return (
    <FormPanel title="Ledger / Lot Entry" onSubmit={(form) => onSubmit(() => createLedger({
      account_id: Number(field(form, "account_id")),
      kind: field(form, "kind"),
      quantity: field(form, "quantity"),
      occurred_at: field(form, "occurred_at"),
      cost_total: field(form, "cost_total") || null,
      cost_currency: field(form, "cost_currency") || null,
      note: field(form, "note"),
      create_lot: field(form, "create_lot") === "on",
    }), "Ledger entry added.")}>
      <select name="account_id" required>
        <option value="">Select account</option>
        {accounts.map((account) => (
          <option key={account.id} value={account.id}>{account.owner} · {programName(programs, account.program_id)}</option>
        ))}
      </select>
      <input name="kind" placeholder="earn | buy | adjustment" required />
      <input name="quantity" placeholder="Signed quantity" required />
      <input name="occurred_at" type="date" required />
      <input name="cost_total" placeholder="Cost total" />
      <input name="cost_currency" placeholder="TWD" />
      <label>
        <input name="create_lot" type="checkbox" /> create cost lot
      </label>
      <input name="note" placeholder="Note" />
    </FormPanel>
  );
}

function TransferRuleForm({ programs, onSubmit }: FormProps & { programs: Program[] }) {
  return (
    <FormPanel title="Transfer Rule" onSubmit={(form) => onSubmit(() => createTransferRule({
      from_program_id: Number(field(form, "from_program_id")),
      to_program_id: Number(field(form, "to_program_id")),
      ratio_from: field(form, "ratio_from"),
      ratio_to: field(form, "ratio_to"),
      bonus_pct: field(form, "bonus_pct") || "0",
      valid_from: field(form, "valid_from"),
      transfer_days_note: field(form, "transfer_days_note"),
    }), "Transfer rule added.")}>
      <ProgramSelect programs={programs} name="from_program_id" />
      <ProgramSelect programs={programs} name="to_program_id" />
      <input name="ratio_from" placeholder="From ratio" required />
      <input name="ratio_to" placeholder="To ratio" required />
      <input name="bonus_pct" placeholder="Bonus %" />
      <input name="valid_from" type="date" required />
      <input name="transfer_days_note" placeholder="Note" />
    </FormPanel>
  );
}

function PurchaseOfferForm({ programs, onSubmit }: FormProps & { programs: Program[] }) {
  return (
    <FormPanel title="Purchase Offer" onSubmit={(form) => onSubmit(() => createPurchaseOffer({
      program_id: Number(field(form, "program_id")),
      kind: field(form, "kind"),
      base_price: field(form, "base_price"),
      currency: field(form, "currency"),
      bonus_pct: field(form, "bonus_pct") || "0",
      start_date: field(form, "start_date"),
      source_note: field(form, "source_note"),
    }), "Purchase offer added.")}>
      <ProgramSelect programs={programs} />
      <input name="kind" placeholder="official | promo | third_party" required />
      <input name="base_price" placeholder="Price per point" required />
      <input name="currency" placeholder="TWD" required />
      <input name="bonus_pct" placeholder="Bonus %" />
      <input name="start_date" type="date" required />
      <input name="source_note" placeholder="Source note" />
    </FormPanel>
  );
}

type FormProps = {
  onSubmit: (action: () => Promise<unknown>, message: string) => Promise<void>;
};

function FormPanel({ title, children, onSubmit }: { title: string; children: ReactNode; onSubmit: (form: HTMLFormElement) => void }) {
  return (
    <form className="form-panel" onSubmit={(event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      onSubmit(event.currentTarget);
      event.currentTarget.reset();
    }}>
      <h2>{title}</h2>
      {children}
      <button className="button button-primary" type="submit">Save</button>
    </form>
  );
}

function ProgramSelect({ programs, name = "program_id" }: { programs: Program[]; name?: string }) {
  return (
    <select name={name} required>
      <option value="">Select program</option>
      {programs.map((program) => (
        <option key={program.id} value={program.id}>{program.name}</option>
      ))}
    </select>
  );
}

function Table({ columns, rows }: { columns: string[]; rows: string[][] }) {
  if (rows.length === 0) return <p className="pending-text">No records yet</p>;
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

function field(form: HTMLFormElement, name: string): string {
  const value = new FormData(form).get(name);
  return typeof value === "string" ? value.trim() : "";
}

function programName(programs: Program[], id: number): string {
  return programs.find((program) => program.id === id)?.name || `Program #${id}`;
}
