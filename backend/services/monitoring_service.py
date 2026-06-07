from sqlalchemy.orm import Session


def get_failed_tasks_paginated(db: Session, page: int, size: int):
    from models.failed_task import FailedTask
    query = db.query(FailedTask).order_by(FailedTask.failed_at.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return total, items
