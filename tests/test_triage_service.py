import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import decision_request, knowledge, triage  # noqa: F401
from shared.services.decision_request_service import create_decision_request
from shared.services.triage_service import (
    create_triage_result,
    get_latest_triage_result_for_request,
    list_triage_results,
    list_triage_results_for_request,
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


def create_request(session):
    return create_decision_request(
        session,
        app_id="capital",
        decision_type="investment",
        question="Should I reduce AVGO exposure?",
        context="AVGO is concentrated.",
        risk_level="high",
        status="submitted",
    )


def test_create_list_and_latest_triage_result():
    session = make_session()
    request = create_request(session)

    first = create_triage_result(
        session,
        decision_request_id=request.id,
        risk_level="high",
        recommendation="escalate_to_brain",
        rationale="High risk.",
        flags=["investment", "high-risk"],
        created_by="triage-agent",
    )
    second = create_triage_result(
        session,
        decision_request_id=request.id,
        risk_level="high",
        recommendation="escalate_to_brain",
        rationale="Manual follow-up.",
        flags="manual,high-risk",
        created_by="human",
    )

    assert list_triage_results(session)[0].id == first.id
    assert len(list_triage_results_for_request(session, request.id)) == 2
    assert get_latest_triage_result_for_request(session, request.id).id == second.id
    assert first.flags == "investment,high-risk"

