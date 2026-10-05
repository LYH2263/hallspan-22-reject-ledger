"""三本互斥账的 API 级语义测试：拒绝账 / 方案账 / 图展示。"""
import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Candidate, Hall, SeatPlan, SeatRejection

REJECTION_KEYS = {"rejection_id", "hall_id", "reason_code", "detail", "persisted", "created_at"}
_codes = itertools.count(1)


@pytest.fixture()
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), Session
    finally:
        app.dependency_overrides.clear()


def add_hall(Session, rows=3, cols=4, min_manhattan=2, closed=False, candidates=0) -> int:
    s = Session()
    try:
        hall = Hall(code=f"H{next(_codes)}", name="测试考室", rows=rows, cols=cols,
                    min_manhattan=min_manhattan, closed=closed)
        s.add(hall)
        s.flush()
        for i in range(candidates):
            s.add(Candidate(hall_id=hall.id, name=f"考生{i}", ticket_no=f"T{i}", paper_id=1 + (i % 3)))
        s.commit()
        return hall.id
    finally:
        s.close()


def counts(Session):
    s = Session()
    try:
        plans = s.scalar(select(func.count()).select_from(SeatPlan))
        rejections = s.scalar(select(func.count()).select_from(SeatRejection))
        return plans, rejections
    finally:
        s.close()


def test_hall_not_found_records_rejection_only(env):
    client, Session = env
    resp = client.post("/api/seating/run?hall_id=999")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body) == REJECTION_KEYS
    assert body["reason_code"] == "HALL_NOT_FOUND"
    assert body["persisted"] is False
    assert body["hall_id"] == 999
    # 方案账不变，拒绝账 +1
    assert counts(Session) == (0, 1)
    assert client.get("/api/seating/plans").json() == []
    rows = client.get("/api/seating/rejections").json()
    assert len(rows) == 1 and rows[0]["reason_code"] == "HALL_NOT_FOUND"


def test_invalid_min_distance_records_rejection_only(env):
    client, Session = env
    hall_id = add_hall(Session, min_manhattan=0, candidates=2)
    resp = client.post(f"/api/seating/run?hall_id={hall_id}")
    assert resp.status_code == 422
    body = resp.json()
    assert set(body) == REJECTION_KEYS
    assert body["reason_code"] == "INVALID_MIN_DISTANCE"
    assert body["persisted"] is False
    assert counts(Session) == (0, 1)


def test_closed_hall_unplaced_records_rejection_only(env):
    client, Session = env
    hall_id = add_hall(Session, rows=2, cols=2, min_manhattan=2, closed=True, candidates=5)
    resp = client.post(f"/api/seating/run?hall_id={hall_id}")
    assert resp.status_code == 409
    body = resp.json()
    assert set(body) == REJECTION_KEYS
    assert body["reason_code"] == "CLOSED_HALL_UNPLACED"
    assert body["persisted"] is False
    assert counts(Session) == (0, 1)
    assert client.get(f"/api/seating/latest?hall_id={hall_id}").status_code == 404


def test_success_writes_plan_and_no_rejection(env):
    client, Session = env
    hall_id = add_hall(Session, rows=3, cols=4, min_manhattan=1, candidates=4)
    resp = client.post(f"/api/seating/run?hall_id={hall_id}")
    assert resp.status_code == 201
    body = resp.json()
    assert body["plan_id"] >= 1
    assert len(body["assignments"]) == 4
    # 成功回包不得携带任何失败码字段
    assert "reason_code" not in body and "persisted" not in body and "rejection_id" not in body
    assert counts(Session) == (1, 0)
    latest = client.get(f"/api/seating/latest?hall_id={hall_id}").json()
    assert latest["plan_id"] == body["plan_id"]


def test_failure_keeps_map_and_stats_unchanged(env):
    client, Session = env
    ok_hall = add_hall(Session, rows=3, cols=4, min_manhattan=1, candidates=4)
    plan_id = client.post(f"/api/seating/run?hall_id={ok_hall}").json()["plan_id"]
    stats_before = client.get(f"/api/seating/stats?hall_id={ok_hall}").json()
    bad_hall = add_hall(Session, rows=2, cols=2, min_manhattan=2, closed=True, candidates=5)
    resp = client.post(f"/api/seating/run?hall_id={bad_hall}")
    assert resp.status_code == 409
    # 图与统计保持操作前，方案账行数不变
    assert client.get(f"/api/seating/latest?hall_id={ok_hall}").json()["plan_id"] == plan_id
    assert client.get(f"/api/seating/stats?hall_id={ok_hall}").json() == stats_before
    assert counts(Session) == (1, 1)


def test_success_does_not_touch_rejection_history(env):
    client, Session = env
    client.post("/api/seating/run?hall_id=999")
    before = client.get("/api/seating/rejections").json()
    hall_id = add_hall(Session, rows=3, cols=4, min_manhattan=1, candidates=4)
    assert client.post(f"/api/seating/run?hall_id={hall_id}").status_code == 201
    after = client.get("/api/seating/rejections").json()
    assert after == before
    assert counts(Session) == (1, 1)


def test_rejection_rows_isomorphic_across_entries(env):
    client, Session = env
    client.post("/api/seating/run?hall_id=999")
    bad_dist = add_hall(Session, min_manhattan=-1, candidates=2)
    client.post(f"/api/seating/run?hall_id={bad_dist}")
    closed = add_hall(Session, rows=2, cols=2, min_manhattan=2, closed=True, candidates=5)
    client.post(f"/api/seating/run?hall_id={closed}")
    rows = client.get("/api/seating/rejections").json()
    assert {r["reason_code"] for r in rows} == {
        "HALL_NOT_FOUND", "INVALID_MIN_DISTANCE", "CLOSED_HALL_UNPLACED"}
    for r in rows:
        assert set(r) == REJECTION_KEYS
        assert r["persisted"] is False
    assert counts(Session) == (0, 3)


def test_latest_is_side_effect_free(env):
    client, Session = env
    assert client.get("/api/seating/latest?hall_id=1").status_code == 404
    assert client.get("/api/seating/stats?hall_id=1").status_code == 200
    assert client.get("/api/seating/violations?hall_id=1").json() == {
        "hall_id": 1, "violations": [], "unplaced": []}
    assert counts(Session) == (0, 0)
