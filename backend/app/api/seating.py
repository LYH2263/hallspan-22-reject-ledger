import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Hall, SeatPlan, SeatRejection
from app.services.seating_run import (
    REASON_CLOSED_HALL_UNPLACED,
    REASON_HALL_NOT_FOUND,
    REASON_INVALID_MIN_DISTANCE,
    execute_run,
    plan_to_response,
    rejection_to_dict,
)

router = APIRouter(prefix="/seating", tags=["seating"])

# 失败入口 → HTTP 状态码；回包体一律为同构拒绝行
REJECTION_STATUS = {
    REASON_HALL_NOT_FOUND: 404,
    REASON_INVALID_MIN_DISTANCE: 422,
    REASON_CLOSED_HALL_UNPLACED: 409,
}

EMPTY_STATS = {"seated": 0, "unplaced": 0, "violations": 0, "capacity": 0}


def _latest_plan(db: Session, hall_id: int) -> SeatPlan | None:
    return db.scalars(
        select(SeatPlan).where(SeatPlan.hall_id == hall_id).order_by(SeatPlan.id.desc())
    ).first()


@router.post("/run", status_code=201)
def run_seating(hall_id: int = 1, db: Session = Depends(get_db)):
    outcome = execute_run(db, hall_id)
    if isinstance(outcome, SeatRejection):
        body = rejection_to_dict(outcome)
        return JSONResponse(status_code=REJECTION_STATUS[outcome.reason_code], content=body)
    return plan_to_response(outcome)


@router.get("/latest")
def latest(hall_id: int = 1, db: Session = Depends(get_db)):
    """图展示：只读方案账，绝不触发排座或写拒绝账。"""
    plan = _latest_plan(db, hall_id)
    if plan is None:
        return JSONResponse(status_code=404, content={"detail": "该考室暂无排座方案"})
    return plan_to_response(plan)


@router.get("/plans")
def plans(hall_id: int | None = None, db: Session = Depends(get_db)):
    """方案账：只含成功写库的方案，失败不在此出现。"""
    stmt = select(SeatPlan).order_by(SeatPlan.id.desc())
    if hall_id is not None:
        stmt = stmt.where(SeatPlan.hall_id == hall_id)
    out = []
    for p in db.scalars(stmt).all():
        data = json.loads(p.result_json)
        out.append({
            "plan_id": p.id,
            "hall_id": p.hall_id,
            "created_at": p.created_at.isoformat(),
            "stats": data.get("stats", EMPTY_STATS),
        })
    return out


@router.get("/rejections")
def rejections(hall_id: int | None = None, db: Session = Depends(get_db)):
    """拒绝账：每次失败一行，可查询；成功不会删减历史拒绝行。"""
    stmt = select(SeatRejection).order_by(SeatRejection.id.desc())
    if hall_id is not None:
        stmt = stmt.where(SeatRejection.hall_id == hall_id)
    return [rejection_to_dict(r) for r in db.scalars(stmt).all()]


@router.get("/violations")
def violations(hall_id: int = 1, db: Session = Depends(get_db)):
    plan = _latest_plan(db, hall_id)
    data = json.loads(plan.result_json) if plan else {}
    return {"hall_id": hall_id, "violations": data.get("violations", []), "unplaced": data.get("unplaced", [])}


@router.get("/stats")
def stats(hall_id: int = 1, db: Session = Depends(get_db)):
    plan = _latest_plan(db, hall_id)
    if plan:
        return {"hall_id": hall_id, **json.loads(plan.result_json).get("stats", EMPTY_STATS)}
    hall = db.get(Hall, hall_id)
    capacity = hall.rows * hall.cols if hall else 0
    return {"hall_id": hall_id, **EMPTY_STATS, "capacity": capacity}
