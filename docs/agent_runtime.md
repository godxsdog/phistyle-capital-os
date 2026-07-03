# Agent Runtime

Date: 2026-07-03

Status: runtime scaffold only. No real LLM calls, background jobs, auth, investment logic, or legacy app integrations are implemented.

## Purpose

The Agent Runtime is the execution engine for PhiStyle OS agents. It provides a neutral layer for registering agents, listing agents, manually running an agent, and recording run results.

The Python package is `phistyle_platform.runtime`. Documentation may still refer to this as the platform runtime layer.

## Current Capabilities

- Register agents in an in-memory registry.
- List registered agents.
- Run an agent manually.
- Store in-memory run results.
- Carry an `AgentRunContext` with an LLM Router instance for future model routing.
- Provide a scheduler placeholder without background jobs.

## Initial Agent

| Agent | Role | Behavior |
| --- | --- | --- |
| `echo-agent` | `test` | Returns the input message with `echo: true`. |

## App and Agent Mapping

The planned App to Agent ownership map lives in `docs/app_agent_mapping.md`.
Capital, Points Wallet, Dental PPT, Travel, Snowboard, and Shared agents should
all enter the system through the Agent Runtime instead of bypassing it.

Legacy apps remain references only until a later integration phase.

## Human Approval

No agent may execute real trades without explicit human confirmation.

This rule should be enforced by the Agent Runtime, not by individual agents.
Early phases are read-only and dry-run only. See `docs/human_approval.md` for the
full architecture rule.

## API

```text
GET /agents
```

Returns registered agents.

```text
POST /agents/run
```

Request:

```json
{
  "agent_id": "echo-agent",
  "input": {
    "message": "hello"
  }
}
```

Response:

```json
{
  "agent_id": "echo-agent",
  "status": "success",
  "output": {
    "message": "hello",
    "echo": true
  }
}
```

## Future Work

- Persist run records to database.
- Add auth and permission checks.
- Add app-scoped execution contexts.
- Add real scheduling.
- Add LLM execution adapters behind the LLM Router.
- Add runtime-level approval gates before any real-world irreversible action.

## Non-Goals

- No real LLM APIs.
- No investment logic.
- No background jobs.
- No legacy app integration.
- No direct app-private file access.
