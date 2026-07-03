# Backend

FastAPI skeleton for PhiStyle OS.

## Current Scope

- Provides `GET /health`.
- Does not implement investment logic.
- Does not implement AI.
- Does not integrate legacy apps.

## Local Run

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```sh
curl http://localhost:8000/health
```
