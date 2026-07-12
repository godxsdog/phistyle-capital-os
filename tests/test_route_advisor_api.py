from datetime import UTC, datetime
from decimal import Decimal

import pytest


pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app, get_session
from shared.database.base import Base
from shared.models import knowledge, point_wallet, route_advisor  # noqa: F401
from shared.models.route_advisor import DestRegion, RouteSweetSpot
from shared.services.point_wallet_service import create_program


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def test_advisor_api_matches_confirmed_rows_and_enforces_review_flow():
    client, session_factory = make_client()
    with session_factory() as session:
        ana = create_program(session, name="ANA", kind="airline")
        document = knowledge.KnowledgeDocument(
            title="合成 ANA 攻略",
            content="僅供測試的合成內容",
            source_type=knowledge.KnowledgeSourceType.IMPORT,
            tags="mileage_guide,sha256:api-synthetic",
            storage_backend=knowledge.StorageBackend.LOCAL,
            file_path="synthetic.txt",
        )
        session.add(document)
        session.flush()
        session.add(DestRegion(airport="NRT", region="日本"))
        pending = RouteSweetSpot(
            program_id=ana.id,
            origin_tag="TPE",
            dest_tag="NRT",
            cabin="business",
            miles_cost=Decimal("45000"),
            tip="合成待確認",
            source_doc_id=document.id,
            status="未確認",
            created_at=datetime.now(UTC),
        )
        confirmed = RouteSweetSpot(
            program_id=ana.id,
            origin_tag="TPE",
            dest_tag="日本",
            cabin="business",
            miles_cost=Decimal("50000"),
            tip="合成已確認",
            source_doc_id=document.id,
            status="已確認",
            created_at=datetime.now(UTC),
        )
        session.add_all([pending, confirmed])
        session.commit()
        pending_id = pending.id
        document_id = document.id

    result = client.get("/wallet/advisor/recommendations?destination=NRT")
    assert result.status_code == 200
    assert [row["tip"] for row in result.json()["recommendations"]] == ["合成已確認"]
    assert result.json()["ai_advice"] is None

    updated = client.patch(
        f"/wallet/advisor/sweet-spots/{pending_id}",
        json={
            "program_id": 1,
            "origin_tag": "TPE",
            "dest_tag": "NRT",
            "cabin": "business",
            "miles_cost": "40000",
            "tip": "人工修正後候選",
            "caveats": None,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["miles_cost"] == "40000"
    assert client.post(
        f"/wallet/advisor/sweet-spots/{pending_id}/status", json={"status": "已確認"}
    ).status_code == 200
    denied_edit = client.patch(
        f"/wallet/advisor/sweet-spots/{pending_id}",
        json={
            "program_id": 1,
            "origin_tag": "TPE",
            "dest_tag": "NRT",
            "cabin": "business",
            "miles_cost": "39000",
            "tip": "不可修改",
            "caveats": None,
        },
    )
    assert denied_edit.status_code == 400
    assert client.get(f"/knowledge/documents/{document_id}").json()["content"] == "僅供測試的合成內容"
    region = client.put("/wallet/advisor/regions/KMQ", json={"region": "日本"})
    assert region.status_code == 200
    assert region.json() == {"airport": "KMQ", "region": "日本"}


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    return TestClient(app), session_factory
