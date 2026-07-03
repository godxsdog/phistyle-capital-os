.PHONY: backend frontend docker-up docker-down health

backend:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

health:
	curl -s http://localhost:8000/health

