import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_session():
    """Create mock database session"""
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    return session


def test_record_failure_creates_failed_task(mock_session):
    """record_failure should create FailedTask record"""
    from src.main import record_failure

    error = ValueError("Test error")
    record_failure(mock_session, 'scrape', 'https://example.com', None, error)

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()

    # Verify the FailedTask was created with correct fields
    call_args = mock_session.add.call_args
    failed_task = call_args[0][0]
    assert failed_task.task_type == 'scrape'
    assert failed_task.article_url == 'https://example.com'
    assert failed_task.exception_type == 'ValueError'
