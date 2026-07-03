from dataclasses import dataclass
import os


DEFAULT_DATABASE_URL = "postgresql+psycopg://phistyle:phistyle@localhost:5432/phistyle_os"


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
    )

