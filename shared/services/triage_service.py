from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.triage import TriageRecommendation, TriageResult, TriageRiskLevel


def create_triage_result(
    session: Session,
    *,
    decision_request_id: int,
    risk_level: str,
    recommendation: str,
    rationale: str,
    flags: list[str] | str | None = None,
    created_by: str,
) -> TriageResult:
    triage_result = TriageResult(
        decision_request_id=decision_request_id,
        risk_level=TriageRiskLevel(risk_level),
        recommendation=TriageRecommendation(recommendation),
        rationale=rationale,
        flags=_serialize_flags(flags),
        created_by=created_by,
    )
    session.add(triage_result)
    session.commit()
    session.refresh(triage_result)
    return triage_result


def list_triage_results(session: Session) -> list[TriageResult]:
    return list(session.scalars(select(TriageResult).order_by(TriageResult.id)))


def list_triage_results_for_request(session: Session, decision_request_id: int) -> list[TriageResult]:
    return list(
        session.scalars(
            select(TriageResult)
            .where(TriageResult.decision_request_id == decision_request_id)
            .order_by(TriageResult.id)
        )
    )


def get_latest_triage_result_for_request(
    session: Session,
    decision_request_id: int,
) -> TriageResult | None:
    return session.scalars(
        select(TriageResult)
        .where(TriageResult.decision_request_id == decision_request_id)
        .order_by(TriageResult.id.desc())
    ).first()


def _serialize_flags(flags: list[str] | str | None) -> str:
    if flags is None:
        return ""
    if isinstance(flags, str):
        return flags
    for flag in flags:
        if "," in flag:
            raise ValueError("Triage flag values must not contain commas")
    return ",".join(flags)

