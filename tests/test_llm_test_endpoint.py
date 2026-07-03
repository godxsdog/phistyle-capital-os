import pytest


fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from backend.app.main import app


def test_llm_test_endpoint_returns_deepseek_dry_run_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.deepseek.local")
    client = TestClient(app)

    response = client.post(
        "/llm/test",
        json={
            "role": "summarizer",
            "prompt": "summarize this",
        },
    )

    assert response.status_code == 200
    assert response.json()["provider_id"] == "deepseek"
    assert response.json()["dry_run"] is True
    assert response.json()["metadata"]["reason"] == "DEEPSEEK_API_KEY is not configured"


def test_llm_test_endpoint_routes_fast_worker_to_deepseek_dry_run(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/llm/test",
        json={
            "role": "fast_worker",
            "prompt": "format this",
        },
    )

    assert response.status_code == 200
    assert response.json()["provider_id"] == "deepseek"


def test_llm_test_endpoint_routes_cheap_bulk_summary_to_deepseek_dry_run(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/llm/test",
        json={
            "role": "cheap_bulk_summary",
            "prompt": "summarize these public notes",
        },
    )

    assert response.status_code == 200
    assert response.json()["provider_id"] == "deepseek"


def test_llm_test_endpoint_orchestrator_returns_fable_dry_run(monkeypatch):
    monkeypatch.delenv("FABLE_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/llm/test",
        json={
            "role": "orchestrator",
            "prompt": "decide this",
        },
    )

    assert response.status_code == 200
    assert response.json()["provider_id"] == "fable"
    assert response.json()["dry_run"] is True
    assert "scaffolded" in response.json()["metadata"]["reason"]

