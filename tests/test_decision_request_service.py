import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import decision_request, knowledge  # noqa: F401
from shared.services.decision_request_service import (
    create_decision_request,
    get_decision_request,
    list_decision_requests,
    update_decision_request_status,
)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_create_list_get_and_update_decision_request_status():
    session = make_session()

    created = create_decision_request(
        session,
        app_id="capital",
        decision_type="investment",
        question="Should I reduce AVGO exposure?",
        context="AVGO is concentrated.",
        options="hold | reduce 20% | hedge",
        risk_level="high",
        status="submitted",
        created_by="Kaichang",
    )

    assert list_decision_requests(session)[0].id == created.id
    assert get_decision_request(session, created.id).question == "Should I reduce AVGO exposure?"

    updated = update_decision_request_status(
        session,
        decision_request_id=created.id,
        status="human_approved",
    )
    assert updated.status.value == "human_approved"


def test_invalid_app_id_rejected_by_service():
    session = make_session()

    with pytest.raises(ValueError, match="Unknown app_id"):
        create_decision_request(
            session,
            app_id="platform",
            decision_type="architecture",
            question="Should platform be an app?",
            context="Not registered yet.",
            risk_level="medium",
            status="draft",
        )

