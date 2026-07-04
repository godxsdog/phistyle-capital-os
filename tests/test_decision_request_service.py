import pytest


pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database.base import Base
from shared.models import decision_request, knowledge  # noqa: F401
from shared.services.decision_request_service import (
    DecisionRequestStatusTransitionError,
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


TERMINAL_TRANSITION_CASES = [
    ("human_approved", "draft"),
    ("human_approved", "submitted"),
    ("human_approved", "triaged"),
    ("human_approved", "brain_reviewed"),
    ("human_approved", "rejected"),
    ("rejected", "draft"),
    ("rejected", "submitted"),
    ("rejected", "triaged"),
    ("rejected", "brain_reviewed"),
    ("rejected", "human_approved"),
    ("archived", "draft"),
    ("archived", "submitted"),
    ("archived", "triaged"),
    ("archived", "brain_reviewed"),
    ("archived", "human_approved"),
    ("archived", "rejected"),
]


@pytest.mark.parametrize(("current_status", "requested_status"), TERMINAL_TRANSITION_CASES)
def test_terminal_status_disallowed_transitions_raise_and_preserve_state(current_status, requested_status):
    session = make_session()
    created = create_decision_request(
        session,
        app_id="capital",
        decision_type="investment",
        question="Should I reduce AVGO exposure?",
        context="AVGO is concentrated.",
        risk_level="high",
        status=current_status,
    )

    with pytest.raises(DecisionRequestStatusTransitionError):
        update_decision_request_status(
            session,
            decision_request_id=created.id,
            status=requested_status,
        )

    session.refresh(created)
    assert created.status.value == current_status


@pytest.mark.parametrize(("current_status", "requested_status"), [
    ("human_approved", "archived"),
    ("rejected", "archived"),
])
def test_allowed_terminal_to_archived_transitions_succeed(current_status, requested_status):
    session = make_session()
    created = create_decision_request(
        session,
        app_id="capital",
        decision_type="investment",
        question="Should I reduce AVGO exposure?",
        context="AVGO is concentrated.",
        risk_level="high",
        status=current_status,
    )

    updated = update_decision_request_status(
        session,
        decision_request_id=created.id,
        status=requested_status,
    )

    assert updated.status.value == requested_status


@pytest.mark.parametrize("status", ["human_approved", "rejected", "archived"])
def test_terminal_same_status_patch_is_noop(status):
    session = make_session()
    created = create_decision_request(
        session,
        app_id="capital",
        decision_type="investment",
        question="Should I reduce AVGO exposure?",
        context="AVGO is concentrated.",
        risk_level="high",
        status=status,
    )

    updated = update_decision_request_status(
        session,
        decision_request_id=created.id,
        status=status,
    )

    assert updated.id == created.id
    assert updated.status.value == status


def test_non_terminal_transition_still_works():
    session = make_session()
    created = create_decision_request(
        session,
        app_id="capital",
        decision_type="investment",
        question="Should I reduce AVGO exposure?",
        context="AVGO is concentrated.",
        risk_level="high",
        status="submitted",
    )

    updated = update_decision_request_status(
        session,
        decision_request_id=created.id,
        status="draft",
    )

    assert updated.status.value == "draft"
