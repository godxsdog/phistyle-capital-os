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

## Non-Goals

- No real LLM APIs.
- No investment logic.
- No background jobs.
- No legacy app integration.
- No direct app-private file access.

