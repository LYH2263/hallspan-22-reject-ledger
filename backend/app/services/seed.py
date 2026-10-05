from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import Candidate, Hall, PaperSet

def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Hall)) or 0) > 0:
        return
    hall = Hall(code="H101", name="一号考室", rows=5, cols=6, min_manhattan=2, closed=False)
    db.add(hall); db.flush()
    papers = [("P-A", "语文 A 卷"), ("P-B", "语文 B 卷"), ("P-C", "语文 C 卷")]
    paper_ids = []
    for code, title in papers:
        p = PaperSet(code=code, title=title)
        db.add(p); db.flush()
        paper_ids.append(p.id)
    names = ["陈一", "李二", "张三", "赵四", "钱五", "孙六", "周七", "吴八", "郑九", "王十", "冯十一", "陈十二"]
    for i, name in enumerate(names):
        db.add(Candidate(hall_id=hall.id, name=name, ticket_no=f"T{2026001+i}",
                         paper_id=paper_ids[i % len(paper_ids)]))
    # 封闭场：2x2 最小距 2 最多落 2 人，5 名考生必触发「全员落座失败」拒绝
    closed_hall = Hall(code="H102", name="二号考室（封闭）", rows=2, cols=2, min_manhattan=2, closed=True)
    db.add(closed_hall); db.flush()
    for i in range(5):
        db.add(Candidate(hall_id=closed_hall.id, name=f"封闭考生{i + 1}", ticket_no=f"T{2026101+i}",
                         paper_id=paper_ids[i % len(paper_ids)]))
    db.commit()
