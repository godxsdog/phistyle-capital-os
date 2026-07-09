from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from phistyle_platform.registry.registry import default_registry
from shared.models.decision_request import (
    DecisionRequest,
    DecisionRequestRiskLevel,
    DecisionRequestStatus,
    DecisionRequestType,
)


TERMINAL_STATUSES = {
    DecisionRequestStatus.HUMAN_APPROVED,
    DecisionRequestStatus.REJECTED,
    DecisionRequestStatus.ARCHIVED,
}
ALLOWED_TERMINAL_TRANSITIONS = {
    (DecisionRequestStatus.HUMAN_APPROVED, DecisionRequestStatus.ARCHIVED),
    (DecisionRequestStatus.REJECTED, DecisionRequestStatus.ARCHIVED),
}


class DecisionRequestStatusTransitionError(ValueError):
    pass


def create_decision_request(
    session: Session,
    *,
    app_id: str,
    decision_type: str,
    question: str,
    context: str,
    options: str | None = None,
    risk_level: str,
    status: str,
    created_by: str | None = None,
    related_knowledge_document_id: int | None = None,
    related_decision_log_id: int | None = None,
    commit: bool = True,
) -> DecisionRequest:
    _validate_app_id(app_id)
    decision_request = DecisionRequest(
        app_id=app_id,
        decision_type=DecisionRequestType(decision_type),
        question=question,
        context=context,
        options=options,
        risk_level=DecisionRequestRiskLevel(risk_level),
        status=DecisionRequestStatus(status),
        created_by=created_by,
        related_knowledge_document_id=related_knowledge_document_id,
        related_decision_log_id=related_decision_log_id,
    )
    session.add(decision_request)
    if commit:
        session.commit()
    else:
        session.flush()
    session.refresh(decision_request)
    return decision_request


def list_decision_requests(session: Session) -> list[DecisionRequest]:
    return list(session.scalars(select(DecisionRequest).order_by(DecisionRequest.id)))


def get_decision_request(session: Session, decision_request_id: int) -> DecisionRequest | None:
    return session.get(DecisionRequest, decision_request_id)


def update_decision_request_status(
    session: Session,
    *,
    decision_request_id: int,
    status: str,
) -> DecisionRequest | None:
    decision_request = get_decision_request(session, decision_request_id)
    if decision_request is None:
        return None
    requested_status = DecisionRequestStatus(status)
    _validate_status_transition(decision_request.status, requested_status)
    decision_request.status = requested_status
    session.commit()
    session.refresh(decision_request)
    return decision_request


def _validate_status_transition(
    current_status: DecisionRequestStatus,
    requested_status: DecisionRequestStatus,
) -> None:
    if current_status == requested_status:
        return
    if current_status not in TERMINAL_STATUSES:
        return
    if (current_status, requested_status) in ALLOWED_TERMINAL_TRANSITIONS:
        return
    raise DecisionRequestStatusTransitionError(
        f"Cannot transition DecisionRequest status from {current_status.value} to {requested_status.value}; "
        "terminal statuses allow only same-status no-op or human_approved/rejected -> archived."
    )


def _validate_app_id(app_id: str) -> None:
    if default_registry.get_app(app_id) is None:
        raise ValueError(f"Unknown app_id: {app_id}")
