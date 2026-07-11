"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { PageHeader } from "../../../../components/ui";
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
      setError("問題、背景、選項與建立者都必填。");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const created = await createCapitalDecision(payload);
      router.push(`/capital/decisions/${created.decision_request_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "建立 Capital 決策失敗。");
      setIsSubmitting(false);
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
          <span>新增</span>
        </nav>

        <PageHeader
          kicker="Capital"
          title="新增決策"
          description="建立結構化投資決策紀錄。分析只會在你進入明細頁後手動啟動。"
        />

        <form className="form-panel" onSubmit={handleSubmit}>
          <p className="subtle">此表單只建立決策請求，不會下單、不會核准交易，也不會自動執行 Brain 分析。</p>
          {error ? <div className="notice notice-error" role="alert">{error}</div> : null}

          <label>
            <span>問題</span>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="是否應該降低 AVGO 部位？"
              required
            />
          </label>

          <label>
            <span>背景</span>
            <textarea
              value={context}
              onChange={(event) => setContext(event.target.value)}
              placeholder="AVGO 目前在投資組合中比重偏高。"
              required
              rows={5}
            />
          </label>

          <label>
            <span>選項</span>
            <input
              value={options}
              onChange={(event) => setOptions(event.target.value)}
              placeholder="持有｜減碼 20%｜避險"
              required
            />
          </label>

          <label>
            <span>風險層級</span>
            <select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value as RiskLevel)}>
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select>
          </label>

          <label>
            <span>建立者</span>
            <input value={createdBy} onChange={(event) => setCreatedBy(event.target.value)} placeholder="Kaichang" required />
          </label>

          <div className="form-actions">
            <Link className="button" href="/capital/decisions">
              取消
            </Link>
            <button className="button button-primary" disabled={isSubmitting} type="submit">
              {isSubmitting ? "建立中..." : "建立決策"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
