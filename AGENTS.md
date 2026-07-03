# Agent Routing Rules

## GPT-5.5
Use only for cross-module architecture, high-risk decisions, database design, investment logic, scoring logic, security, and final review.

Do not use GPT-5.5 for formatting, comments, docs, rename, boilerplate, simple tests, or batch replacement.

## Codex
Use for implementation, local code modification, diffs, refactors, tests, and bug fixes.

## Mini
Use for comments, markdown, formatting, renaming, type hints, docs, and low-risk batch changes.

## Workflow
GPT-5.5 plans -> Codex implements -> Mini/Codex reviews -> GPT-5.5 reviews only if risky.

Never paste full logs to GPT-5.5. Summarize first.
