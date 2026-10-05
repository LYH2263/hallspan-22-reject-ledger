"""三账互斥：失败走拒绝账（方案账/图不变），成功走方案账（拒绝账不动）。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Candidate, Hall, PaperSet, SeatPlan, SeatRejection

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

REJECTION_KEYS = {"id", "hall_id", "reason_code", "detail", "persisted", "created_at"}


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    db.add(Hall(id=1, code="H1", name="一考室", rows=5, cols=6, min_manhattan=2))
    db.add(PaperSet(id=1, code="P-A", title="语文 A 卷"))
    db.flush()
    for i in range(4):
        db.add(Candidate(hall_id=1, name=f"考生{i}", ticket_no=f"T{i}", paper_id=1))
    db.commit()
    db.close()
    yield


def counts():
    db = TestingSession()
    try:
        plans = db.scalar(select(func.count()).select_from(SeatPlan))
        rejs = db.scalar(select(func.count()).select_from(SeatRejection))
        return plans, rejs
    finally:
        db.close()


def test_hall_not_found_writes_rejection_only():
    r = client.post("/api/seating/run", params={"hall_id": 999})
    assert r.status_code == 422
    body = r.json()
    assert set(body) == REJECTION_KEYS
    assert body["reason_code"] == "HALL_NOT_FOUND"
    assert body["persisted"] is False
    assert counts() == (0, 1)
    rows = client.get("/api/seating/rejections", params={"hall_id": 999}).json()
    assert len(rows) == 1 and rows[0]["reason_code"] == "HALL_NOT_FOUND"


def test_invalid_min_distance_writes_rejection_only():
    r = client.post("/api/seating/run", params={"hall_id": 1, "min_manhattan": 0})
    assert r.status_code == 422
    body = r.json()
    assert set(body) == REJECTION_KEYS
    assert body["reason_code"] == "INVALID_MIN_DISTANCE"
    assert body["persisted"] is False
    assert counts() == (0, 1)


def test_unplaced_full_house_failure_writes_rejection_only():
    # 5x6 网格最大曼哈顿距离 9，要求 10 必然无法全员落座
    r = client.post("/api/seating/run", params={"hall_id": 1, "min_manhattan": 10})
    assert r.status_code == 422
    body = r.json()
    assert set(body) == REJECTION_KEYS
    assert body["reason_code"] == "UNPLACED_CANDIDATES"
    assert body["persisted"] is False
    assert counts() == (0, 1)


def test_success_writes_plan_only_and_carries_no_failure_code():
    r = client.post("/api/seating/run", params={"hall_id": 1})
    assert r.status_code == 200
    body = r.json()
    assert "reason_code" not in body and "persisted" not in body
    assert len(body["assignments"]) == 4 and body["unplaced"] == []
    assert counts() == (1, 0)
    assert client.get("/api/seating/latest", params={"hall_id": 1}).json()["id"] == body["id"]


def test_failure_keeps_plan_map_stats_and_success_keeps_rejections():
    p1 = client.post("/api/seating/run", params={"hall_id": 1}).json()["id"]
    stats_before = client.get("/api/seating/stats", params={"hall_id": 1}).json()
    assert counts() == (1, 0)

    client.post("/api/seating/run", params={"hall_id": 1, "min_manhattan": 0})
    client.post("/api/seating/run", params={"hall_id": 999})
    assert counts() == (1, 2)  # 失败不涨方案账
    latest = client.get("/api/seating/latest", params={"hall_id": 1}).json()
    assert latest["id"] == p1  # 图保持操作前
    assert client.get("/api/seating/stats", params={"hall_id": 1}).json() == stats_before

    p2 = client.post("/api/seating/run", params={"hall_id": 1}).json()["id"]
    assert p2 != p1
    assert counts() == (2, 2)  # 成功不删减历史拒绝行
    assert client.get("/api/seating/latest", params={"hall_id": 1}).json()["id"] == p2


def test_rejection_rows_isomorphic_across_entries():
    client.post("/api/seating/run", params={"hall_id": 999})
    client.post("/api/seating/run", params={"hall_id": 1, "min_manhattan": -3})
    client.post("/api/seating/run", params={"hall_id": 1, "min_manhattan": 10})
    rows = client.get("/api/seating/rejections").json()
    assert len(rows) == 3
    assert all(set(r) == REJECTION_KEYS for r in rows)
    assert all(r["persisted"] is False for r in rows)
    assert {r["reason_code"] for r in rows} == {
        "HALL_NOT_FOUND", "INVALID_MIN_DISTANCE", "UNPLACED_CANDIDATES"}
