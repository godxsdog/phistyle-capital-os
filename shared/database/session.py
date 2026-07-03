from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker

from shared.database.connection import create_database_engine


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

