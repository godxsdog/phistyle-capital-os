# DeepSeek Setup

Date: 2026-07-03

Status: DeepSeek is the first real LLM provider for low-risk text tasks. Fable remains scaffold-only.

## Purpose

DeepSeek powers low-risk text workflows while the OS keeps high-risk orchestration separate.

Current DeepSeek routes:

- `summarizer`
- `fast_worker`
- `cheap_bulk_summary`

Current non-DeepSeek behavior:

- `orchestrator` returns dry-run Fable metadata and does not call Fable.
- Fable API keys are not required.

## Environment

Set these in a local `.env` or server environment. Do not commit real keys.

```text
DEEPSEEK_API_KEY=your-local-secret
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

If `DEEPSEEK_API_KEY` is missing, `/llm/test` returns a clear dry-run response and does not make a network call.

## Test Endpoint

```http
POST /llm/test
```

Request:

```json
{
  "role": "summarizer",
  "prompt": "summarize this..."
}
```

Dry-run response shape:

```json
{
  "provider_id": "deepseek",
  "model": "deepseek-chat",
  "dry_run": true,
  "content": "[dry-run:deepseek] summarize this...",
  "metadata": {
    "role": "summarizer",
    "base_url": "https://api.deepseek.com",
    "reason": "DEEPSEEK_API_KEY is not configured"
  }
}
```

## Security Rules

- Never commit API keys.
- Do not log API keys.
- Do not send secrets, `.env` files, medical data, private repo contents, or sensitive financial data to low-risk test endpoints.
- Use `/llm/test` only for controlled provider validation.

## Non-Goals

- No Fable calls.
- No investment logic.
- No legacy app changes.
- No production prompt workflows.

