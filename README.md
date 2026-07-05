# PhiStyle Capital OS

AI-first investment operating system.

Goal: identify events that materially change investment decisions, not summarize all news.

Runtime expects Python >=3.10; the local development venv and backend image use Python 3.12.

Core principles:
- AI infrastructure first
- CapEx driven
- Supply-chain transmission
- Capital flow first
- Evidence before opinion

## Environment Files

- `.env.example` is committed as the template for required environment values.
- `.env` is local-only and is loaded by Docker Compose for real runtime secrets.
- `.env` must never be committed.
