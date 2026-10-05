"""排座运行编排：方案账与拒绝账互斥落库。

- 成功：只新增 SeatPlan（方案账），不新增拒绝行。
- 失败：只新增 SeatRejection（拒绝账，persisted=False），方案表行数不变。
两条路径互斥，不存在“失败仍插方案”或“成功带失败码”的第三态。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Candidate, Hall, SeatPlan, SeatRejection
from app.services.seat_engine import find_violations, place_candidates, plan_to_dict

# 拒绝原因码：所有失败入口共用同一套字段（同构拒绝行）
REASON_HALL_NOT_FOUND = "HALL_NOT_FOUND"            # 考室不存在
REASON_INVALID_MIN_DISTANCE = "INVALID_MIN_DISTANCE"  # 非法最小距
REASON_CLOSED_HALL_UNPLACED = "CLOSED_HALL_UNPLACED"  # 封闭场全员落座失败


def record_rejection(db: Session, hall_id: int, reason_code: str, detail: str) -> SeatRejection:
    """失败唯一出口：落一行拒绝账，绝不触碰方案表。"""
    rej = SeatRejection(
        hall_id=hall_id,
        reason_code=reason_code,
        detail=detail,
        persisted=False,
        created_at=datetime.utcnow(),
    )
    db.add(rej)
    db.commit()
    db.refresh(rej)
    return rej


def execute_run(db: Session, hall_id: int) -> SeatPlan | SeatRejection:
    """执行一次排座。返回 SeatPlan（成功）或 SeatRejection（失败），二者必居其一。"""
    hall = db.get(Hall, hall_id)
    if hall is None:
        return record_rejection(db, hall_id, REASON_HALL_NOT_FOUND, f"考室 {hall_id} 不存在")
    if hall.min_manhattan < 1:
        return record_rejection(
            db, hall_id, REASON_INVALID_MIN_DISTANCE,
            f"非法最小距 min_manhattan={hall.min_manhattan}（须 ≥ 1）",
        )
    cands = [
        {"id": c.id, "name": c.name, "ticket_no": c.ticket_no, "paper_id": c.paper_id}
        for c in db.scalars(select(Candidate).where(Candidate.hall_id == hall_id)).all()
    ]
    assigns, unplaced = place_candidates(hall.rows, hall.cols, hall.min_manhattan, cands)
    if hall.closed and unplaced:
        return record_rejection(
            db, hall_id, REASON_CLOSED_HALL_UNPLACED,
            f"封闭场未全员落座：{len(unplaced)} 人未排上，方案未写库",
        )
    viols = find_violations(hall.rows, hall.cols, hall.min_manhattan, assigns)
    result = plan_to_dict(assigns, unplaced, viols, hall.rows, hall.cols)
    result["hall"] = {"id": hall.id, "name": hall.name, "min_manhattan": hall.min_manhattan}
    plan = SeatPlan(
        hall_id=hall_id,
        created_at=datetime.utcnow(),
        result_json=json.dumps(result, ensure_ascii=False),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def rejection_to_dict(rej: SeatRejection) -> dict:
    """拒绝账行的对外形状：所有失败入口同构。"""
    return {
        "rejection_id": rej.id,
        "hall_id": rej.hall_id,
        "reason_code": rej.reason_code,
        "detail": rej.detail,
        "persisted": rej.persisted,
        "created_at": rej.created_at.isoformat(),
    }


def plan_to_response(plan: SeatPlan) -> dict:
    """方案账行的对外形状：只含排座结果，不含任何失败码字段。"""
    data = json.loads(plan.result_json)
    return {"plan_id": plan.id, **data}
