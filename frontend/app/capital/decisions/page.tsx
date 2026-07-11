"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DataTable, EmptyState, PageHeader, StatusChip } from "../../../components/ui";
import { CapitalDecisionListItem, listCapitalDecisions } from "../../../lib/capitalApi";
import { RISK_LABELS, formatDateZh, labelFor } from "../../../lib/displayConstants";

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
        setError(err instanceof Error ? err.message : "讀取 Capital 決策失敗。");
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="麵包屑">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <span>交易決策</span>
        </nav>

        <PageHeader
          kicker="Capital"
          title="交易決策"
          description="建立與審查 Capital 投資決策紀錄；分析管線只在你明確啟動後才會執行。"
          actions={
            <Link className="button button-primary" href="/capital/decisions/new">
              新增決策
            </Link>
          }
        />

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
          <EmptyState
            title="尚無交易決策"
            description="先建立一筆決策紀錄；管線不會自動執行，也不會自動交易。"
            actionHref="/capital/decisions/new"
            actionLabel="新增決策"
          />
        ) : (
          <section className="panel" aria-label="交易決策列表">
            <DataTable
              columns={["編號", "問題", "風險", "狀態", "建立者", "建立日期", "操作"]}
              rows={decisions.map((decision) => [
                `#${decision.id}`,
                decision.question,
                labelFor(RISK_LABELS, decision.risk_level),
                <StatusChip key={decision.id} value={decision.status} />,
                decision.created_by || "未設定",
                formatDateZh(decision.created_at),
                <Link key={`link-${decision.id}`} className="button" href={`/capital/decisions/${decision.id}`}>
                  開啟
                </Link>,
              ])}
            />
          </section>
        )}
      </div>
    </main>
  );
}
