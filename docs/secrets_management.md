# Secrets Management

Date: 2026-07-03

Status: architecture rule. This document describes expected handling before more
automation is added. It does not add provider calls or deployment automation.

## Principles

- Real secrets live in `.env` on the Mac mini only.
- `.env` must never be committed.
- `.env.example` may contain placeholder keys only.
- API keys, tokens, passwords, and private URLs must never appear in logs, test
  output, docs, screenshots, error messages, or normalized/serialized objects.

## Deployment Shape

The server should load secrets through Docker Compose `env_file` once the runtime
uses real providers:

```yaml
services:
  backend:
    env_file:
      - .env
```

The deploy flow remains:

```text
MacBook -> git push -> ssh Mac mini -> deploy script -> docker compose
```

Only source code and placeholder examples move through GitHub. The Mac mini keeps
the real `.env` file outside version control.

## Provider Keys

Provider adapters must read keys from environment variables at runtime. They must
not print keys, serialize keys, include keys in exceptions, or expose keys through
health/debug endpoints.
