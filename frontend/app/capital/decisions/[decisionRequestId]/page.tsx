"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CapitalDecisionSummary,
  getCapitalDecision,
  runCapitalDecision,
  submitHumanReview,
} from "../../../../lib/capitalApi";

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
      setError(err instanceof Error ? err.message : "Unable to load Capital decision.");
    } finally {
      setIsLoading(false);
    }
  }, [decisionRequestId]);

  useEffect(() => {
    if (!Number.isFinite(decisionRequestId)) {
      setError("Invalid decision id.");
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
      setError(err instanceof Error ? err.message : "Unable to run Capital analysis.");
    } finally {
      setIsRunning(false);
    }
  }

  async function handleReview(decision: "approve" | "reject") {
    if (!summary?.decision_log || reviewAction) return;
    const normalizedReviewer = reviewer.trim();
    if (!normalizedReviewer) {
      setError("Reviewer is required before final review.");
      return;
    }
    const message =
      decision === "approve"
        ? "This records the decision as approved. It does not execute a trade or any external action."
        : "This records the decision as rejected. It does not execute any external action.";
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
      setError(err instanceof Error ? err.message : "Unable to submit human review.");
    } finally {
      setReviewAction(null);
    }
  }

  return (
    <main>
      <div className="shell">
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link href="/">PhiStyle OS</Link>
          <span>/</span>
          <Link href="/capital/decisions">Capital Decisions</Link>
          <span>/</span>
          <span>#{Number.isFinite(decisionRequestId) ? decisionRequestId : "unknown"}</span>
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
            <section className="page-header">
              <div>
                <div className="section-kicker">Capital Decision</div>
                <h1>#{summary.decision_request.id}</h1>
                <p>{summary.decision_request.question}</p>
              </div>
              {!summary.decision_log && !isFinalized ? (
                <button className="button button-primary" disabled={isRunning} onClick={handleRunPipeline} type="button">
                  {isRunning ? "Running..." : "Run Analysis"}
                </button>
              ) : null}
            </section>

            {error ? <div className="notice notice-error" role="alert">{error}</div> : null}

            <section className="timeline" aria-label="Capital decision stages">
              <Stage title="Decision Request" state={stageForDecisionRequest(summary.decision_request.status)}>
                <DataGrid
                  items={[
                    ["Question", summary.decision_request.question],
                    ["Context", summary.decision_request.context],
                    ["Options", summary.decision_request.options || "none"],
                    ["Risk level", summary.decision_request.risk_level],
                    ["Status", summary.decision_request.status],
                  ]}
                />
              </Stage>

              <Stage title="Triage" state={summary.triage_result ? "completed" : "pending"}>
                {summary.triage_result ? (
                  <DataGrid
                    items={[
                      ["ID", String(summary.triage_result.id)],
                      ["Recommendation", summary.triage_result.recommendation],
                    ]}
                  />
                ) : (
                  <PendingText />
                )}
              </Stage>

              <Stage title="Brain Review" state={summary.brain_review ? "completed" : "pending"}>
                {summary.brain_review ? (
                  <>
                    <DataGrid
                      items={[
                        ["ID", String(summary.brain_review.id)],
                        ["Recommendation", summary.brain_review.recommendation],
                        ["Confidence", summary.brain_review.confidence],
                      ]}
                    />
                    <p className="subtle">BrainReview remains advisory.</p>
                  </>
                ) : (
                  <PendingText />
                )}
              </Stage>

              <Stage title="Decision Log" state={stageForDecisionLog(summary.decision_log?.status)}>
                {summary.decision_log ? (
                  <DataGrid
                    items={[
                      ["ID", String(summary.decision_log.id)],
                      ["Status", summary.decision_log.status],
                      ["Approved by", summary.decision_log.approved_by || "none"],
                    ]}
                  />
                ) : (
                  <PendingText />
                )}
              </Stage>

              <Stage title="Human Review" state={stageForHumanReview(summary)}>
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
          {summary.human_review.review_decision === "approve" ? "Approved Decision Record" : "Rejected Decision Record"}
        </div>
        <DataGrid
          items={[
            ["Reviewer", summary.human_review.reviewer],
            ["Review decision", summary.human_review.review_decision],
          ]}
        />
      </>
    );
  }

  if (!summary.decision_log) {
    return <PendingText />;
  }

  if (summary.decision_log.status !== "proposed" || !summary.requires_human_review) {
    return <p className="subtle">No active human review action is available for this decision.</p>;
  }

  return (
    <div className="review-form">
      <p className="subtle">HumanReview is explicit and record-only. Approval or rejection does not execute trades or external actions.</p>
      <label>
        <span>Reviewer</span>
        <input value={reviewer} onChange={(event) => onReviewerChange(event.target.value)} placeholder="Kaichang" />
      </label>
      <label>
        <span>Comment optional</span>
        <textarea
          value={comment}
          onChange={(event) => onCommentChange(event.target.value)}
          placeholder="Optional review note"
          rows={3}
        />
      </label>
      <div className="form-actions">
        <button className="button button-approve" disabled={isSubmitting} onClick={() => onReview("approve")} type="button">
          {reviewAction === "approve" ? "Approving..." : "Approve"}
        </button>
        <button className="button button-danger" disabled={isSubmitting} onClick={() => onReview("reject")} type="button">
          {reviewAction === "reject" ? "Rejecting..." : "Reject"}
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
        <span className={`stage-pill stage-pill-${state}`}>{state}</span>
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
  return <p className="pending-text">Pending</p>;
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
