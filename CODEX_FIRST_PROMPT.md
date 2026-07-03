You are my Staff Software Engineer.

We are building an AI investment operating system called PhiStyle Capital OS.

Your first job is to scaffold the project only. Do not implement business logic.

Requirements:
1. Use the provided seed files as project constitution.
2. Create a production-ready monorepo structure.
3. Include:
   - backend: FastAPI
   - frontend: Next.js
   - database: PostgreSQL, SQLAlchemy, Alembic
   - queue/cache: Redis
   - vector store: Qdrant
   - automation: n8n
   - LLM UI: Open WebUI
4. Generate docker-compose.yml.
5. Create folders:
   - backend
   - frontend
   - agents
   - prompts
   - workflows
   - scripts
   - database
   - dashboard
   - tests
   - config
   - docs
6. Do not create fake investment algorithms.
7. Do not overengineer.
8. Every file should have meaningful documentation.
9. Prepare for multi-agent architecture.
10. After scaffolding, stop and wait for the next task.

Important:
- GPT-5.5 is only for architecture and high-risk review.
- Codex is responsible for implementation and diffs.
- Mini models are for docs, comments, formatting, and low-risk batch tasks.
