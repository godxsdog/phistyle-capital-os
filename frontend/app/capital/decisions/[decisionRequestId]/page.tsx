"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader, StatusChip } from "../../../../components/ui";
import {
  CapitalDecisionSummary,
  getCapitalDecision,
  runCapitalDecision,
  submitHumanReview,
} from "../../../../lib/capitalApi";
import {
  RECOMMENDATION_LABELS,
  REVIEW_DECISION_LABELS,
  RISK_LABELS,
  STATUS_LABELS,
  labelFor,
} from "../../../../lib/displayConstants";

export default function CapitalDecisionDetailPage() {
  const params = useParams<{ decisionRequestId: string }>();
  const decisionRequestId = Number(params.decisionRequestId);
  const [summary, setSummary] = useState<CapitalDecisionSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [reviewAction, setReviewAction] = useState<"approve" | "reject" | null>(null);
  const [reviewer, setReviewer] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadDecision = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setSummary(await getCapitalDecision(decisionRequestId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "讀取 Capital 決策失敗。");
    } finally {
      setIsLoading(false);
    }
  }, [decisionRequestId]);

  useEffect(() => {
    if (!Number.isFinite(decisionRequestId)) {
      setError("決策編號不正確。");
      setIsLoading(false);
      return;
    }
    void loadDecision();
  }, [decisionRequestId, loadDecision]);

  const isFinalized = useMemo(() => {
    if (!summary) return false;
    return Boolean(
      summary.human_review ||
        summary.decision_log?.status === "approved" ||
        summary.decision_log?.status === "rejected" ||
        summary.decision_request.status === "human_approved" ||
        summary.decision_request.status === "rejected" ||
        summary.decision_request.status === "archived",
    );
  }, [summary]);

  async function handleRunPipeline() {
    if (!summary || isRunning || isFinalized) return;
    setIsRunning(true);
    setError(null);
    try {
      await runCapitalDecision(decisionRequestId);
      await loadDecision();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "執行 Capital 分析失敗。");
    } finally {
      setIsRunning(false);
    }
  }

  async function handleReview(decision: "approve" | "reject") {
    if (!summary?.decision_log || reviewAction) return;
    const normalizedReviewer = reviewer.trim();
    if (!normalizedReviewer) {
      setError("送出最終審查前，請填寫審查人。");
      return;
    }
    const message =
      decision === "approve"
        ? "這只會把決策紀錄為核准，不會下單，也不會執行任何外部動作。"
        : "這只會把決策紀錄為拒絕，不會執行任何外部動作。";
    if (!window.confirm(message)) {
      return;
    }

    setReviewAction(decision);
    setError(null);
    try {
      const normalizedComment = comment.trim();
      await submitHumanReview(summary.decision_log.id, {
        reviewer: normalizedReviewer,
        review_decision: decision,
        ...(normalizedComment ? { comment: normalizedComment } : {}),
      });
      await loadDecision();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "送出人工審查失敗。");
    } finally {
      setReviewAction(null);
    }
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="麵包屑">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <Link href="/capital/decisions">交易決策</Link>
          <span>/</span>
          <span>#{Number.isFinite(decisionRequestId) ? decisionRequestId : "未知"}</span>
        </nav>

        {isLoading ? (
          <section className="panel" aria-live="polite">
            <div className="loading-block" />
            <div className="loading-block" />
            <div className="loading-block short" />
          </section>
        ) : error && !summary ? (
          <section className="notice notice-error" role="alert">
            {error}
          </section>
        ) : summary ? (
          <>
            <PageHeader
              kicker="Capital 決策明細"
              title={`#${summary.decision_request.id}`}
              description={summary.decision_request.question}
              actions={!summary.decision_log && !isFinalized ? (
                <button className="button button-primary" disabled={isRunning} onClick={handleRunPipeline} type="button">
                  {isRunning ? "分析中..." : "執行分析"}
                </button>
              ) : null}
            />

            {error ? <div className="notice notice-error" role="alert">{error}</div> : null}

            <DecisionProgress summary={summary} />

            <section className="decision-stage-cards" aria-label="Capital 決策階段明細">
              <Stage title="決策請求" state={stageForDecisionRequest(summary.decision_request.status)}>
                <DataGrid
                  items={[
                    ["問題", summary.decision_request.question],
                    ["背景", summary.decision_request.context],
                    ["選項", summary.decision_request.options || "無"],
                    ["風險層級", labelFor(RISK_LABELS, summary.decision_request.risk_level)],
                    ["狀態", labelFor(STATUS_LABELS, summary.decision_request.status)],
                  ]}
                />
              </Stage>

              <Stage title="分流" state={summary.triage_result ? "completed" : "pending"}>
                {summary.triage_result ? (
                  <DataGrid
                    items={[
                      ["編號", String(summary.triage_result.id)],
                      ["建議", labelFor(RECOMMENDATION_LABELS, summary.triage_result.recommendation)],
                    ]}
                  />
                ) : (
                  <PendingText />
                )}
              </Stage>

              <Stage title="Brain 審查" state={summary.brain_review ? "completed" : "pending"}>
                {summary.brain_review ? (
                  <>
                    <DataGrid
                      items={[
                        ["編號", String(summary.brain_review.id)],
                        ["建議", labelFor(RECOMMENDATION_LABELS, summary.brain_review.recommendation)],
                        ["信心", summary.brain_review.confidence],
                        ["LLM 狀態", brainReviewLlmStatus(summary.brain_review)],
                      ]}
                    />
                    <p className="subtle">Brain 審查只提供建議，不代表核准或執行。</p>
                  </>
                ) : (
                  <PendingText />
                )}
              </Stage>

              <Stage title="決策紀錄" state={stageForDecisionLog(summary.decision_log?.status)}>
                {summary.decision_log ? (
                  <DataGrid
                    items={[
                      ["編號", String(summary.decision_log.id)],
                      ["狀態", labelFor(STATUS_LABELS, summary.decision_log.status)],
                      ["核准 metadata", summary.decision_log.approved_by || "無"],
                    ]}
                  />
                ) : (
                  <PendingText />
                )}
              </Stage>

              <Stage title="人工審查" state={stageForHumanReview(summary)}>
                <HumanReviewSection
                  comment={comment}
                  isSubmitting={reviewAction !== null}
                  onCommentChange={setComment}
                  onReview={handleReview}
                  onReviewerChange={setReviewer}
                  reviewer={reviewer}
                  reviewAction={reviewAction}
                  summary={summary}
                />
              </Stage>
            </section>
          </>
        ) : null}
      </div>
    </main>
  );
}

function DecisionProgress({ summary }: { summary: CapitalDecisionSummary }) {
  const stages = [
    { label: "建立", state: stageForDecisionRequest(summary.decision_request.status) },
    { label: "分析", state: summary.triage_result ? "completed" as const : "pending" as const },
    { label: "審查", state: summary.brain_review ? "completed" as const : "pending" as const },
    { label: "核准", state: stageForDecisionLog(summary.decision_log?.status) },
    { label: "結案", state: stageForHumanReview(summary) },
  ];
  return (
    <ol className="decision-progress" aria-label="決策進度">
      {stages.map((stage) => (
        <li className={`progress-${stage.state}`} key={stage.label}>
          <span aria-hidden="true" />
          <strong>{stage.label}</strong>
        </li>
      ))}
    </ol>
  );
}

function HumanReviewSection({
  comment,
  isSubmitting,
  onCommentChange,
  onReview,
  onReviewerChange,
  reviewer,
  reviewAction,
  summary,
}: {
  comment: string;
  isSubmitting: boolean;
  onCommentChange: (value: string) => void;
  onReview: (decision: "approve" | "reject") => void;
  onReviewerChange: (value: string) => void;
  reviewer: string;
  reviewAction: "approve" | "reject" | null;
  summary: CapitalDecisionSummary;
}) {
  if (summary.human_review) {
    return (
      <>
        <div className={`final-banner final-${summary.human_review.review_decision}`}>
          {summary.human_review.review_decision === "approve" ? "已核准決策紀錄" : "已拒絕決策紀錄"}
        </div>
        <DataGrid
          items={[
            ["審查人", summary.human_review.reviewer],
            ["審查結果", labelFor(REVIEW_DECISION_LABELS, summary.human_review.review_decision)],
          ]}
        />
      </>
    );
  }

  if (!summary.decision_log) {
    return <PendingText />;
  }

  if (summary.decision_log.status !== "proposed" || !summary.requires_human_review) {
    return <p className="subtle">此決策目前沒有可執行的人工審查動作。</p>;
  }

  return (
    <div className="review-form">
      <p className="subtle">人工審查是明確且只記錄的步驟；核准或拒絕都不會下單或執行外部動作。</p>
      <label>
        <span>審查人</span>
        <input value={reviewer} onChange={(event) => onReviewerChange(event.target.value)} placeholder="Kaichang" />
      </label>
      <label>
        <span>備註（選填）</span>
        <textarea
          value={comment}
          onChange={(event) => onCommentChange(event.target.value)}
          placeholder="可填寫審查補充說明；目前 Capital 摘要不會顯示此備註。"
          rows={3}
        />
      </label>
      <div className="form-actions">
        <button className="button button-approve" disabled={isSubmitting} onClick={() => onReview("approve")} type="button">
          {reviewAction === "approve" ? "核准中..." : "核准"}
        </button>
        <button className="button button-danger" disabled={isSubmitting} onClick={() => onReview("reject")} type="button">
          {reviewAction === "reject" ? "拒絕中..." : "拒絕"}
        </button>
      </div>
    </div>
  );
}

function Stage({
  children,
  state,
  title,
}: {
  children: React.ReactNode;
  state: "pending" | "completed" | "approved" | "rejected";
  title: string;
}) {
  return (
    <article className={`stage stage-${state}`}>
      <div className="stage-header">
        <h2>{title}</h2>
        <StatusChip value={state} />
      </div>
      {children}
    </article>
  );
}

function DataGrid({ items }: { items: Array<[string, string]> }) {
  return (
    <dl className="data-grid">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function PendingText() {
  return <p className="pending-text">待處理</p>;
}

function brainReviewLlmStatus(summary: NonNullable<CapitalDecisionSummary["brain_review"]>): string {
  if (summary.llm_backed) {
    return summary.llm_model ? `LLM 支援（${summary.llm_model}）` : "LLM 支援";
  }
  return `規則 fallback：${summary.llm_fallback_reason || "未執行"}`;
}

function stageForDecisionRequest(status: string): "pending" | "completed" | "approved" | "rejected" {
  if (status === "human_approved") return "approved";
  if (status === "rejected") return "rejected";
  return "completed";
}

function stageForDecisionLog(status: string | undefined): "pending" | "completed" | "approved" | "rejected" {
  if (!status) return "pending";
  if (status === "approved") return "approved";
  if (status === "rejected") return "rejected";
  return "completed";
}

function stageForHumanReview(summary: CapitalDecisionSummary): "pending" | "completed" | "approved" | "rejected" {
  if (summary.human_review?.review_decision === "approve") return "approved";
  if (summary.human_review?.review_decision === "reject") return "rejected";
  if (summary.decision_log?.status === "approved") return "approved";
  if (summary.decision_log?.status === "rejected") return "rejected";
  if (!summary.human_review) return "pending";
  return "completed";
}
