"""拒绝账：所有排座失败入口统一落拒绝行，字段同构，永不删改。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import SeatRejection

# 失败原因码：成功响应中禁止出现
HALL_NOT_FOUND = "HALL_NOT_FOUND"
INVALID_MIN_DISTANCE = "INVALID_MIN_DISTANCE"
UNPLACED_CANDIDATES = "UNPLACED_CANDIDATES"


def record_rejection(db: Session, hall_id: int, reason_code: str, detail: str) -> SeatRejection:
    """落一条拒绝行并提交。persisted 恒为 False：拒绝账不声称写库。"""
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


def rejection_to_dict(rej: SeatRejection) -> dict:
    return {
        "id": rej.id,
        "hall_id": rej.hall_id,
        "reason_code": rej.reason_code,
        "detail": rej.detail,
        "persisted": rej.persisted,
        "created_at": rej.created_at.isoformat() if rej.created_at else None,
    }
