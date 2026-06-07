"""Unit tests for backend/services/llm_provider_service.py"""
import uuid
from unittest.mock import MagicMock, patch

import pytest


def _mock_provider(**kwargs):
    p = MagicMock()
    p.id = kwargs.get("id", uuid.uuid4())
    p.model = kwargs.get("model", "gemini-test")
    p.type = kwargs.get("type", "llm")
    p.priority = kwargs.get("priority", 1)
    p.is_active = kwargs.get("is_active", True)
    return p


def _usage_row(model_used: str, cnt: int):
    r = MagicMock()
    r.model_used = model_used
    r.cnt = cnt
    return r


def _make_db(all_return=None, first_return=None):
    """Build a mock DB whose .query(…) chain supports .order_by, .filter, .group_by."""
    db = MagicMock()
    q = db.query.return_value
    q.order_by.return_value.all.return_value = all_return or []
    q.filter.return_value.all.return_value = all_return or []
    q.filter.return_value.first.return_value = first_return
    q.filter.return_value.group_by.return_value.all.return_value = []
    # _check_priority_conflict with exclude_id does filter().filter().first()
    # Default to None (no conflict) so tests that don't expect a conflict pass.
    q.filter.return_value.filter.return_value.first.return_value = None
    return db, q


def _patch_analysis_col(mock_analysis):
    """Configure MockAnalysis.analyzed_at to support >= datetime comparisons."""
    col = MagicMock()
    type(col).__ge__ = lambda self, other: MagicMock()
    mock_analysis.analyzed_at = col


# ---------------------------------------------------------------------------
# get_providers / _attach_usage
# ---------------------------------------------------------------------------

def test_get_providers_attaches_usage_count():
    from backend.services.llm_provider_service import get_providers

    p = _mock_provider(model="gemini-flash")
    db, q = _make_db()
    q.order_by.return_value.all.return_value = [p]
    q.filter.return_value.group_by.return_value.all.return_value = [_usage_row("gemini-flash", 7)]

    with patch("models.llm_provider.LlmProvider"), patch("models.analysis.Analysis") as MockAnalysis:
        _patch_analysis_col(MockAnalysis)
        result = get_providers(db)

    assert result[0].usage_24h == 7


def test_get_providers_zero_usage_when_no_analyses():
    from backend.services.llm_provider_service import get_providers

    p = _mock_provider(model="no-use-model")
    db, q = _make_db()
    q.order_by.return_value.all.return_value = [p]
    q.filter.return_value.group_by.return_value.all.return_value = []

    with patch("models.llm_provider.LlmProvider"), patch("models.analysis.Analysis") as MockAnalysis:
        _patch_analysis_col(MockAnalysis)
        result = get_providers(db)

    assert result[0].usage_24h == 0


def test_get_providers_empty():
    from backend.services.llm_provider_service import get_providers

    db, q = _make_db()
    q.order_by.return_value.all.return_value = []

    with patch("models.llm_provider.LlmProvider"), patch("models.analysis.Analysis") as MockAnalysis:
        _patch_analysis_col(MockAnalysis)
        result = get_providers(db)

    assert result == []


# ---------------------------------------------------------------------------
# create_provider
# ---------------------------------------------------------------------------

def test_create_provider_success():
    from backend.services.llm_provider_service import create_provider
    from backend.schemas.llm_provider import LlmProviderCreate

    data = LlmProviderCreate(
        name="gemini", model="gemini-2-flash", type="llm",
        api_key_env="GEMINI_API_KEY", priority=1,
    )
    mock_obj = _mock_provider()
    db, q = _make_db(first_return=None)

    with patch("models.llm_provider.LlmProvider") as MockLP:
        MockLP.return_value = mock_obj
        result = create_provider(db, data)

    db.add.assert_called_once_with(mock_obj)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(mock_obj)
    assert result.usage_24h == 0


def test_create_provider_priority_conflict_raises_409():
    from backend.services.llm_provider_service import create_provider
    from backend.schemas.llm_provider import LlmProviderCreate
    from fastapi import HTTPException

    data = LlmProviderCreate(
        name="gemini", model="gemini-2-flash", type="llm",
        api_key_env="KEY", priority=1,
    )
    db, q = _make_db(first_return=_mock_provider())  # conflict exists

    with patch("models.llm_provider.LlmProvider"):
        with pytest.raises(HTTPException) as exc:
            create_provider(db, data)

    assert exc.value.status_code == 409
    db.add.assert_not_called()


# ---------------------------------------------------------------------------
# update_provider
# ---------------------------------------------------------------------------

def test_update_provider_success():
    from backend.services.llm_provider_service import update_provider
    from backend.schemas.llm_provider import LlmProviderUpdate

    pid = uuid.uuid4()
    existing = _mock_provider(id=pid, priority=1, type="llm")
    db, q = _make_db(first_return=existing)
    # _check_priority_conflict with exclude_id uses filter().filter().first()
    # _make_db already sets that chain to None (no conflict).

    with patch("models.llm_provider.LlmProvider"):
        result = update_provider(db, pid, LlmProviderUpdate(is_active=False))

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(existing)
    assert result is existing


def test_update_provider_not_found_returns_none():
    from backend.services.llm_provider_service import update_provider
    from backend.schemas.llm_provider import LlmProviderUpdate

    db, q = _make_db(first_return=None)

    with patch("models.llm_provider.LlmProvider"):
        result = update_provider(db, uuid.uuid4(), LlmProviderUpdate(is_active=False))

    assert result is None
    db.commit.assert_not_called()


def test_update_provider_priority_conflict_raises_409():
    from backend.services.llm_provider_service import update_provider
    from backend.schemas.llm_provider import LlmProviderUpdate
    from fastapi import HTTPException

    pid = uuid.uuid4()
    existing = _mock_provider(id=pid, priority=1, type="llm")
    conflicting = _mock_provider(priority=2, type="llm")
    db, q = _make_db(first_return=existing)
    # _check_priority_conflict with exclude_id: filter().filter().first() → conflicting
    q.filter.return_value.filter.return_value.first.return_value = conflicting

    with patch("models.llm_provider.LlmProvider"):
        with pytest.raises(HTTPException) as exc:
            update_provider(db, pid, LlmProviderUpdate(priority=2))

    assert exc.value.status_code == 409
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# delete_provider
# ---------------------------------------------------------------------------

def test_delete_provider_success():
    from backend.services.llm_provider_service import delete_provider

    pid = uuid.uuid4()
    mock_obj = _mock_provider(id=pid)
    db, q = _make_db(first_return=mock_obj)

    with patch("models.llm_provider.LlmProvider"):
        result = delete_provider(db, pid)

    db.delete.assert_called_once_with(mock_obj)
    db.commit.assert_called_once()
    assert result is True


def test_delete_provider_not_found_returns_false():
    from backend.services.llm_provider_service import delete_provider

    db, q = _make_db(first_return=None)

    with patch("models.llm_provider.LlmProvider"):
        result = delete_provider(db, uuid.uuid4())

    assert result is False
    db.delete.assert_not_called()


# ---------------------------------------------------------------------------
# reorder_providers
# ---------------------------------------------------------------------------

def test_reorder_providers_success():
    from backend.services.llm_provider_service import reorder_providers

    p1 = _mock_provider(id=uuid.uuid4(), priority=1, type="llm", model="m1")
    p2 = _mock_provider(id=uuid.uuid4(), priority=2, type="llm", model="m2")
    priorities = {p1.id: 10, p2.id: 20}

    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value.all.return_value = [p1, p2]
    q.filter.return_value.first.return_value = None  # no conflict
    q.filter.return_value.group_by.return_value.all.return_value = []  # _attach_usage

    with patch("models.llm_provider.LlmProvider"), patch("models.analysis.Analysis") as MockAnalysis:
        _patch_analysis_col(MockAnalysis)
        result = reorder_providers(db, priorities)

    assert p1.priority == 10
    assert p2.priority == 20
    db.commit.assert_called_once()
    assert len(result) == 2


def test_reorder_providers_duplicate_values_raises_400():
    from backend.services.llm_provider_service import reorder_providers
    from fastapi import HTTPException

    priorities = {uuid.uuid4(): 5, uuid.uuid4(): 5}  # duplicate priority value

    db = MagicMock()
    with patch("models.llm_provider.LlmProvider"):
        with pytest.raises(HTTPException) as exc:
            reorder_providers(db, priorities)

    assert exc.value.status_code == 400


def test_reorder_providers_provider_not_found_raises_404():
    from backend.services.llm_provider_service import reorder_providers
    from fastapi import HTTPException

    p1_id = uuid.uuid4()
    priorities = {p1_id: 1, uuid.uuid4(): 2}  # 2 IDs requested, only 1 in DB

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [_mock_provider(id=p1_id)]

    with patch("models.llm_provider.LlmProvider"):
        with pytest.raises(HTTPException) as exc:
            reorder_providers(db, priorities)

    assert exc.value.status_code == 404


def test_reorder_providers_external_conflict_raises_409():
    from backend.services.llm_provider_service import reorder_providers
    from fastapi import HTTPException

    p1 = _mock_provider(id=uuid.uuid4(), priority=1, type="llm")
    priorities = {p1.id: 5}

    conflicting = _mock_provider(priority=5, type="llm", model="external")

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [p1]
    db.query.return_value.filter.return_value.first.return_value = conflicting

    with patch("models.llm_provider.LlmProvider"):
        with pytest.raises(HTTPException) as exc:
            reorder_providers(db, priorities)

    assert exc.value.status_code == 409
