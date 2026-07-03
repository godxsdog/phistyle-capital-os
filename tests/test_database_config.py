from backend.app.core.config import DEFAULT_DATABASE_URL, get_settings


def test_database_url_defaults_to_local_postgres(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert get_settings().database_url == DEFAULT_DATABASE_URL


def test_database_url_can_be_loaded_from_env(monkeypatch):
    database_url = "postgresql+psycopg://user:pass@db:5432/example"
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert get_settings().database_url == database_url

