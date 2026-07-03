# Database

Date: 2026-07-03

Status: persistence scaffold only. No investment logic, ingestion, legacy integration, or real data has been added.

## Purpose

The database core prepares PhiStyle OS for persistent storage across apps, platform modules, services, and agents.

Current scope:

- PostgreSQL service in Docker Compose.
- SQLAlchemy engine/session scaffold.
- Alembic migration scaffold.
- Initial table models only.
- Backend config reads `DATABASE_URL` from environment.

## Environment

Local default:

```text
DATABASE_URL=postgresql+psycopg://phistyle:phistyle@localhost:5432/phistyle_os
```

Docker backend default:

```text
DATABASE_URL=postgresql+psycopg://phistyle:phistyle@postgres:5432/phistyle_os
```

## Initial Models

| Model | Purpose |
| --- | --- |
| `Company` | Company identity metadata. No scoring or investment logic. |
| `Watchlist` | Named watchlist container. No selection logic. |
| `Event` | Generic event record for future workflows. No news parsing. |
| `AgentRun` | Audit-friendly record of future agent execution metadata. No model execution. |

## Alembic

Migration scaffold lives in:

```text
migrations/
```

Create a future migration with:

```sh
alembic revision --autogenerate -m "initial database"
```

Apply migrations with:

```sh
alembic upgrade head
```

## Run Postgres Locally

```sh
docker compose up -d postgres
```

The database data is stored in the `postgres_data` Docker volume.

## Non-Goals

- No investment logic.
- No scoring logic.
- No data ingestion.
- No legacy app migration.
- No app registry persistence yet.
- No production security policy yet.

