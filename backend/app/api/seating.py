import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Candidate, Hall, SeatPlan, SeatRejection
from app.services.rejections import (
    HALL_NOT_FOUND,
    INVALID_MIN_DISTANCE,
    UNPLACED_CANDIDATES,
    record_rejection,
    rejection_to_dict,
)
from app.services.seat_engine import find_violations, place_candidates, plan_to_dict

router = APIRouter(prefix="/seating", tags=["seating"])


def _reject(db: Session, hall_id: int, reason_code: str, detail: str) -> JSONResponse:
    """失败唯一出口：落拒绝账，返回 422 + 拒绝行。绝不写方案账。"""
    rej = record_rejection(db, hall_id, reason_code, detail)
    return JSONResponse(status_code=422, content=rejection_to_dict(rej))


@router.post("/run")
def run_seating(hall_id: int = 1, min_manhattan: int | None = None, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        return _reject(db, hall_id, HALL_NOT_FOUND, f"考室 {hall_id} 不存在")
    min_dist = min_manhattan if min_manhattan is not None else hall.min_manhattan
    if min_dist < 1:
        return _reject(db, hall_id, INVALID_MIN_DISTANCE, f"非法最小曼哈顿距离 {min_dist}，必须 ≥ 1")
    cands = [{"id": c.id, "name": c.name, "ticket_no": c.ticket_no, "paper_id": c.paper_id}
             for c in db.scalars(select(Candidate).where(Candidate.hall_id == hall_id)).all()]
    assigns, unplaced = place_candidates(hall.rows, hall.cols, min_dist, cands)
    if unplaced:
        names = "、".join(c["name"] for c in unplaced)
        return _reject(db, hall_id, UNPLACED_CANDIDATES,
                       f"封闭考室要求全员落座，{len(unplaced)} 人未能排座：{names}")
    viols = find_violations(hall.rows, hall.cols, min_dist, assigns)
    result = plan_to_dict(assigns, unplaced, viols, hall.rows, hall.cols)
    result["hall"] = {"id": hall.id, "name": hall.name, "min_manhattan": min_dist}
    plan = SeatPlan(hall_id=hall_id, created_at=datetime.utcnow(), result_json=json.dumps(result, ensure_ascii=False))
    db.add(plan); db.commit(); db.refresh(plan)
    return {"id": plan.id, **result}


@router.get("/rejections")
def rejections(hall_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(SeatRejection).order_by(SeatRejection.id.desc())
    if hall_id is not None:
        stmt = stmt.where(SeatRejection.hall_id == hall_id)
    return [rejection_to_dict(r) for r in db.scalars(stmt).all()]


@router.get("/latest")
def latest(hall_id: int = 1, db: Session = Depends(get_db)):
    plan = db.scalars(select(SeatPlan).where(SeatPlan.hall_id == hall_id).order_by(SeatPlan.id.desc())).first()
    if not plan:
        raise HTTPException(404, "暂无排座方案")
    data = json.loads(plan.result_json)
    return {"id": plan.id, **data}


@router.get("/violations")
def violations(hall_id: int = 1, db: Session = Depends(get_db)):
    data = latest(hall_id=hall_id, db=db)
    return {"hall_id": hall_id, "violations": data.get("violations", []), "unplaced": data.get("unplaced", [])}


@router.get("/stats")
def stats(hall_id: int = 1, db: Session = Depends(get_db)):
    data = latest(hall_id=hall_id, db=db)
    return {"hall_id": hall_id, **data.get("stats", {})}
