# Daily Brief Agent

Date: 2026-07-03

Status: skeleton implementation only.

## Purpose

Daily Brief Agent summarizes provided text into a short structured brief. It is
the first PhiStyle OS agent intended to use the LLM Router summarizer route.

## Agent

| Field | Value |
| --- | --- |
| Agent id | `daily-brief-agent` |
| Name | Daily Brief Agent |
| Role | `summarizer` |
| Source | `manual_input` |

## Input

```json
{
  "topic": "AI infrastructure",
  "text": "long text to summarize"
}
```

## Output

```json
{
  "topic": "AI infrastructure",
  "summary": "...",
  "key_points": [],
  "risk_flags": [],
  "source": "manual_input"
}
```

## LLM Routing

The agent asks the LLM Router for the `summarizer` role. The current route uses
DeepSeek through the existing provider adapter path.

Tests mock the provider call. They do not make network requests.

## Non-Goals

- No external news fetching.
- No investment scoring.
- No trading.
- No database persistence.
- No scheduling.
- No Fable calls.
- No legacy app integration.

