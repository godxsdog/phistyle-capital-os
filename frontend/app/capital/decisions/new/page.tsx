"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { createCapitalDecision } from "../../../../lib/capitalApi";

type RiskLevel = "low" | "medium" | "high";

export default function NewCapitalDecisionPage() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");
  const [options, setOptions] = useState("");
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("high");
  const [createdBy, setCreatedBy] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = {
      question: question.trim(),
      context: context.trim(),
      options: options.trim(),
      risk_level: riskLevel,
      created_by: createdBy.trim(),
    };

    if (!payload.question || !payload.context || !payload.options || !payload.created_by) {
      setError("Question, context, options, and created by are required.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const created = await createCapitalDecision(payload);
      router.push(`/capital/decisions/${created.decision_request_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to create Capital decision.");
      setIsSubmitting(false);
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
          <span>New</span>
        </nav>

        <section className="page-header">
          <div>
            <div className="section-kicker">Capital</div>
            <h1>New Decision</h1>
            <p>Create a structured investment decision record. Analysis runs only after you open the detail page and start it.</p>
          </div>
        </section>

        <form className="form-panel" onSubmit={handleSubmit}>
          {error ? <div className="notice notice-error" role="alert">{error}</div> : null}

          <label>
            <span>Question</span>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Should I reduce AVGO exposure?"
              required
            />
          </label>

          <label>
            <span>Context</span>
            <textarea
              value={context}
              onChange={(event) => setContext(event.target.value)}
              placeholder="AVGO is now concentrated in the portfolio."
              required
              rows={5}
            />
          </label>

          <label>
            <span>Options</span>
            <input
              value={options}
              onChange={(event) => setOptions(event.target.value)}
              placeholder="hold | reduce 20% | hedge"
              required
            />
          </label>

          <label>
            <span>Risk level</span>
            <select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value as RiskLevel)}>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
            </select>
          </label>

          <label>
            <span>Created by</span>
            <input
              value={createdBy}
              onChange={(event) => setCreatedBy(event.target.value)}
              placeholder="Kaichang"
              required
            />
          </label>

          <div className="form-actions">
            <Link className="button" href="/capital/decisions">
              Cancel
            </Link>
            <button className="button button-primary" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Creating..." : "Create Decision"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
