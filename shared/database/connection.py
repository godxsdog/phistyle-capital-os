from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine


DEFAULT_DATABASE_URL = "postgresql+psycopg://phistyle:phistyle@localhost:5432/phistyle_os"


def get_database_url(database_url: str | None = None) -> str:
    return database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_database_engine(database_url: str | None = None, **kwargs) -> Engine:
    return create_engine(
        get_database_url(database_url),
        pool_pre_ping=True,
        future=True,
        **kwargs,
    )
