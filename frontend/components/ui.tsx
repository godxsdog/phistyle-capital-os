import Link from "next/link";
import { ReactNode } from "react";
import { STATUS_LABELS, labelFor } from "../lib/displayConstants";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`ui-card ${className}`.trim()}>{children}</section>;
}

export function KpiCard({
  label,
  value,
  note,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  tone?: "neutral" | "accent" | "gain" | "loss" | "warning";
}) {
  return (
    <Card className={`kpi-card kpi-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {note ? <small>{note}</small> : null}
    </Card>
  );
}

export function PageHeader({
  kicker,
  title,
  description,
  actions,
}: {
  kicker?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <section className="page-header">
      <div>
        {kicker ? <div className="section-kicker">{kicker}</div> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </section>
  );
}

export function DataTable({
  columns,
  rows,
  emptyLabel = "目前沒有資料",
}: {
  columns: string[];
  rows: ReactNode[][];
  emptyLabel?: string;
}) {
  if (rows.length === 0) {
    return <p className="pending-text">{emptyLabel}</p>;
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StatusChip({ value, tone }: { value: string | null | undefined; tone?: string }) {
  const normalized = (value || "pending").toLowerCase();
  const resolvedTone = tone || toneForStatus(normalized);
  return <span className={`status-chip status-chip-${resolvedTone}`}>{labelFor(STATUS_LABELS, normalized)}</span>;
}

export function EmptyState({
  title,
  description,
  actionHref,
  actionLabel,
}: {
  title: string;
  description?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {actionHref && actionLabel ? (
        <Link className="button button-primary" href={actionHref}>
          {actionLabel}
        </Link>
      ) : null}
    </div>
  );
}

function toneForStatus(value: string): string {
  if (["approved", "human_approved", "active", "success", "open"].includes(value)) return "success";
  if (["rejected", "failed", "expired"].includes(value)) return "danger";
  if (["submitted", "triaged", "brain_reviewed", "pending"].includes(value)) return "warning";
  return "neutral";
}
