"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { FormEvent, useEffect, useState } from "react";
import {
  AwardAvailability,
  AwardWatch,
  LoyaltyProgram,
  PointBalance,
  TransferPartner,
  ValuationRate,
  WalletPortfolio,
  createAvailability,
  createBalance,
  createProgram,
  createTransfer,
  createValuation,
  createWatch,
  fetchWatch,
  getPortfolio,
  listAvailability,
  listBalances,
  listPrograms,
  listTransfers,
  listValuations,
  listWatches,
  seedWalletDefaults,
} from "../../lib/walletApi";
import styles from "./WalletPage.module.css";

export default function WalletPage() {
  const [programs, setPrograms] = useState<LoyaltyProgram[]>([]);
  const [balances, setBalances] = useState<PointBalance[]>([]);
  const [valuations, setValuations] = useState<ValuationRate[]>([]);
  const [transfers, setTransfers] = useState<TransferPartner[]>([]);
  const [watches, setWatches] = useState<AwardWatch[]>([]);
  const [availability, setAvailability] = useState<AwardAvailability[]>([]);
  const [portfolio, setPortfolio] = useState<WalletPortfolio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    void loadWallet();
  }, []);

  async function loadWallet() {
    try {
      const [nextPrograms, nextBalances, nextValuations, nextTransfers, nextWatches, nextAvailability, nextPortfolio] =
        await Promise.all([
          listPrograms(),
          listBalances(),
          listValuations(),
          listTransfers(),
          listWatches(),
          listAvailability(),
          getPortfolio(),
        ]);
      setPrograms(nextPrograms);
      setBalances(nextBalances);
      setValuations(nextValuations);
      setTransfers(nextTransfers);
      setWatches(nextWatches);
      setAvailability(nextAvailability);
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
            <div className="section-kicker">Travel Finance</div>
            <h1>Point Wallet</h1>
            <p>Track point balances, editable valuations, transfer paths, expiry risk, and watched award availability.</p>
          </div>
          <button className="button" onClick={() => submit(seedWalletDefaults, "Editable defaults seeded.")} type="button">
            Seed Defaults
          </button>
        </section>
        {error ? <div className="notice notice-error">{error}</div> : null}
        {status ? <p className="subtle">{status}</p> : null}
        <section className="panel">
          <h2>Portfolio</h2>
          <div className="data-grid">
            <div>
              <dt>Total TWD Value</dt>
              <dd>{portfolio?.total_value_twd ?? "0"}</dd>
            </div>
            <div>
              <dt>Expiring Soon</dt>
              <dd>{portfolio?.expiring_soon.length ?? 0}</dd>
            </div>
          </div>
          <Table columns={["Program", "Balance", "Rate", "Value", "Expires"]} rows={(portfolio?.programs || []).map((row) => [
            String(row.program_name),
            String(row.balance),
            String(row.twd_per_point || "none"),
            String(row.value_twd || "none"),
            String(row.expires_at || "none"),
          ])} />
        </section>
        <div className={styles.grid}>
          <ProgramForm onSubmit={submit} />
          <BalanceForm programs={programs} onSubmit={submit} />
          <ValuationForm programs={programs} onSubmit={submit} />
          <TransferForm programs={programs} onSubmit={submit} />
          <WatchForm programs={programs} onSubmit={submit} />
          <ManualAvailabilityForm watches={watches} onSubmit={submit} />
        </div>
        <section className="panel">
          <h2>Transfer Map</h2>
          <Table columns={["From", "To", "Ratio", "Days", "Notes"]} rows={transfers.map((row) => [
            programName(programs, row.from_program_id),
            programName(programs, row.to_program_id),
            `${row.ratio_from}:${row.ratio_to}`,
            row.transfer_days || "",
            row.notes || "",
          ])} />
        </section>
        <section className="panel">
          <h2>Award Watches</h2>
          <Table columns={["Route", "Cabin", "Program", "Fetch"]} rows={watches.map((watch) => [
            `${watch.origin}-${watch.destination}`,
            watch.cabin,
            watch.program_id ? programName(programs, watch.program_id) : "any",
            "Use button below",
          ])} />
          <div className="form-actions">
            {watches.map((watch) => (
              <button key={watch.id} className="button" type="button" onClick={() => submit(() => fetchWatch(watch.id), `Fetched watch #${watch.id}.`)}>
                Fetch #{watch.id}
              </button>
            ))}
          </div>
        </section>
        <section className="panel">
          <h2>Award Availability</h2>
          <Table columns={["Watch", "Seen", "Flight", "Program", "Seats", "Miles", "Source"]} rows={availability.map((row) => [
            String(row.watch_id),
            row.seen_date,
            row.flight_date,
            row.program,
            String(row.seats || ""),
            String(row.miles_cost || ""),
            row.source,
          ])} />
        </section>
      </div>
    </main>
  );
}

function ProgramForm({ onSubmit }: { onSubmit: (action: () => Promise<unknown>, message: string) => Promise<void> }) {
  return (
    <FormPanel title="Program" onSubmit={(form) => onSubmit(() => createProgram({
      name: field(form, "name"),
      kind: field(form, "kind"),
      notes: field(form, "notes"),
    }), "Program added.")}>
      <input name="name" placeholder="Program name" required />
      <input name="kind" placeholder="airline | hotel | bank | other" required />
      <input name="notes" placeholder="Notes" />
    </FormPanel>
  );
}

function BalanceForm({ programs, onSubmit }: { programs: LoyaltyProgram[]; onSubmit: (action: () => Promise<unknown>, message: string) => Promise<void> }) {
  return (
    <FormPanel title="Balance Snapshot" onSubmit={(form) => onSubmit(() => createBalance({
      program_id: Number(field(form, "program_id")),
      balance: field(form, "balance"),
      as_of: field(form, "as_of"),
      expires_at: field(form, "expires_at") || null,
      note: field(form, "note"),
    }), "Balance snapshot added.")}>
      <ProgramSelect programs={programs} />
      <input name="balance" placeholder="Balance" required />
      <input name="as_of" type="date" required />
      <input name="expires_at" type="date" />
      <input name="note" placeholder="Note" />
    </FormPanel>
  );
}

function ValuationForm({ programs, onSubmit }: { programs: LoyaltyProgram[]; onSubmit: (action: () => Promise<unknown>, message: string) => Promise<void> }) {
  return (
    <FormPanel title="Valuation" onSubmit={(form) => onSubmit(() => createValuation({
      program_id: Number(field(form, "program_id")),
      twd_per_point: field(form, "twd_per_point"),
      effective_date: field(form, "effective_date"),
      source: field(form, "source"),
    }), "Valuation added.")}>
      <ProgramSelect programs={programs} />
      <input name="twd_per_point" placeholder="TWD per point" required />
      <input name="effective_date" type="date" required />
      <input name="source" placeholder="editable defaults, not market truth" />
    </FormPanel>
  );
}

function TransferForm({ programs, onSubmit }: { programs: LoyaltyProgram[]; onSubmit: (action: () => Promise<unknown>, message: string) => Promise<void> }) {
  return (
    <FormPanel title="Transfer Partner" onSubmit={(form) => onSubmit(() => createTransfer({
      from_program_id: Number(field(form, "from_program_id")),
      to_program_id: Number(field(form, "to_program_id")),
      ratio_from: Number(field(form, "ratio_from")),
      ratio_to: Number(field(form, "ratio_to")),
      transfer_days: field(form, "transfer_days"),
      notes: field(form, "notes"),
    }), "Transfer partner added.")}>
      <ProgramSelect programs={programs} name="from_program_id" />
      <ProgramSelect programs={programs} name="to_program_id" />
      <div className={styles.inline}>
        <input name="ratio_from" placeholder="From ratio" required />
        <input name="ratio_to" placeholder="To ratio" required />
      </div>
      <input name="transfer_days" placeholder="Transfer days" />
      <input name="notes" placeholder="Notes" />
    </FormPanel>
  );
}

function WatchForm({ programs, onSubmit }: { programs: LoyaltyProgram[]; onSubmit: (action: () => Promise<unknown>, message: string) => Promise<void> }) {
  return (
    <FormPanel title="Award Watch" onSubmit={(form) => onSubmit(() => createWatch({
      origin: field(form, "origin"),
      destination: field(form, "destination"),
      cabin: field(form, "cabin"),
      program_id: field(form, "program_id") ? Number(field(form, "program_id")) : null,
    }), "Award watch added.")}>
      <div className={styles.inline}>
        <input name="origin" placeholder="TPE" required />
        <input name="destination" placeholder="LAX" required />
      </div>
      <input name="cabin" placeholder="business" required />
      <ProgramSelect programs={programs} includeAny />
    </FormPanel>
  );
}

function ManualAvailabilityForm({ watches, onSubmit }: { watches: AwardWatch[]; onSubmit: (action: () => Promise<unknown>, message: string) => Promise<void> }) {
  return (
    <FormPanel title="Manual Availability" onSubmit={(form) => onSubmit(() => createAvailability({
      watch_id: Number(field(form, "watch_id")),
      seen_date: field(form, "seen_date"),
      flight_date: field(form, "flight_date"),
      program: field(form, "program"),
      seats: field(form, "seats") ? Number(field(form, "seats")) : null,
      miles_cost: field(form, "miles_cost") || null,
      taxes_fees: field(form, "taxes_fees"),
      source: "manual",
    }), "Manual availability added.")}>
      <select name="watch_id" required>
        <option value="">Select watch</option>
        {watches.map((watch) => (
          <option key={watch.id} value={watch.id}>{watch.origin}-{watch.destination} {watch.cabin}</option>
        ))}
      </select>
      <input name="seen_date" type="date" required />
      <input name="flight_date" type="date" required />
      <input name="program" placeholder="Program" required />
      <div className={styles.inline}>
        <input name="seats" placeholder="Seats" />
        <input name="miles_cost" placeholder="Miles" />
      </div>
      <input name="taxes_fees" placeholder="Taxes/fees" />
    </FormPanel>
  );
}

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

function ProgramSelect({ programs, includeAny = false, name = "program_id" }: { programs: LoyaltyProgram[]; includeAny?: boolean; name?: string }) {
  return (
    <select name={name} required={!includeAny}>
      {includeAny ? <option value="">Any program</option> : <option value="">Select program</option>}
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

function programName(programs: LoyaltyProgram[], id: number): string {
  return programs.find((program) => program.id === id)?.name || `Program #${id}`;
}
