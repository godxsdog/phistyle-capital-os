"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CapitalDecisionListItem, listCapitalDecisions } from "../../../lib/capitalApi";

export default function CapitalDecisionsPage() {
  const [decisions, setDecisions] = useState<CapitalDecisionListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    listCapitalDecisions()
      .then((items) => {
        if (!isMounted) return;
        setDecisions(items);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Unable to load Capital decisions.");
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>Capital Decisions</span>
        </nav>

        <section className="page-header">
          <div>
            <div className="section-kicker">Capital</div>
            <h1>Capital Decisions</h1>
            <p>Create and review Capital investment decision records through the advisory pipeline.</p>
          </div>
          <Link className="button button-primary" href="/capital/decisions/new">
            New Decision
          </Link>
        </section>

        {isLoading ? (
          <section className="panel" aria-live="polite">
            <div className="loading-block" />
            <div className="loading-block short" />
          </section>
        ) : error ? (
          <section className="notice notice-error" role="alert">
            {error}
          </section>
        ) : decisions.length === 0 ? (
          <section className="empty-state">
            <h2>No Capital decisions yet</h2>
            <p>Create a decision record first. The pipeline will only run after you explicitly start it.</p>
            <Link className="button button-primary" href="/capital/decisions/new">
              New Decision
            </Link>
          </section>
        ) : (
          <section className="decision-list" aria-label="Capital decision list">
            {decisions.map((decision) => (
              <Link className="decision-row" href={`/capital/decisions/${decision.id}`} key={decision.id}>
                <div>
                  <div className="row-title">#{decision.id} {decision.question}</div>
                  <div className="row-meta">
                    <span>{decision.risk_level}</span>
                    <span>{decision.status}</span>
                    <span>{decision.created_by || "unknown creator"}</span>
                    <span>{formatDate(decision.created_at)}</span>
                  </div>
                </div>
                <span aria-hidden="true">→</span>
              </Link>
            ))}
          </section>
        )}
      </div>
    </main>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}
