"""Unit tests for backend/services/monitoring_service.py"""
import uuid
from unittest.mock import MagicMock, patch


def _mock_task(**kwargs):
    t = MagicMock()
    t.id = kwargs.get("id", uuid.uuid4())
    t.article_id = kwargs.get("article_id", uuid.uuid4())
    t.exception = kwargs.get("exception", "ValueError: test error")
    t.resolved = kwargs.get("resolved", False)
    return t


def test_get_failed_tasks_returns_total_and_items():
    from backend.services.monitoring_service import get_failed_tasks_paginated

    task = _mock_task()
    db = MagicMock()
    q = db.query.return_value
    q.order_by.return_value = q
    q.count.return_value = 1
    q.offset.return_value.limit.return_value.all.return_value = [task]

    with patch("models.failed_task.FailedTask"):
        total, items = get_failed_tasks_paginated(db, page=1, size=10)

    assert total == 1
    assert items == [task]


def test_get_failed_tasks_pagination_offset():
    from backend.services.monitoring_service import get_failed_tasks_paginated

    db = MagicMock()
    q = db.query.return_value
    q.order_by.return_value = q
    q.count.return_value = 20
    q.offset.return_value.limit.return_value.all.return_value = []

    with patch("models.failed_task.FailedTask"):
        get_failed_tasks_paginated(db, page=3, size=5)

    # page=3, size=5 → offset=(3-1)*5=10, limit=5
    q.offset.assert_called_with(10)
    q.offset.return_value.limit.assert_called_with(5)


def test_get_failed_tasks_empty_db():
    from backend.services.monitoring_service import get_failed_tasks_paginated

    db = MagicMock()
    q = db.query.return_value
    q.order_by.return_value = q
    q.count.return_value = 0
    q.offset.return_value.limit.return_value.all.return_value = []

    with patch("models.failed_task.FailedTask"):
        total, items = get_failed_tasks_paginated(db, page=1, size=10)

    assert total == 0
    assert items == []


def test_get_failed_tasks_multiple_pages():
    from backend.services.monitoring_service import get_failed_tasks_paginated

    tasks = [_mock_task() for _ in range(3)]
    db = MagicMock()
    q = db.query.return_value
    q.order_by.return_value = q
    q.count.return_value = 13
    q.offset.return_value.limit.return_value.all.return_value = tasks

    with patch("models.failed_task.FailedTask"):
        total, items = get_failed_tasks_paginated(db, page=2, size=10)

    assert total == 13
    assert items == tasks
    q.offset.assert_called_with(10)  # (2-1)*10
