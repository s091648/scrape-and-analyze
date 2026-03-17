import pytest
from unittest.mock import MagicMock, patch
import uuid


def test_record_failure_creates_failed_task():
    """record_failure should create a FailedTask record"""
    with patch('src.main.FailedTask') as MockFailedTask:
        from src.main import record_failure

        mock_session = MagicMock()
        mock_instance = MagicMock()
        MockFailedTask.return_value = mock_instance

        error = ValueError("Test error message")
        record_failure(mock_session, 'scrape', 'https://example.com', None, error)

        # Verify FailedTask was created with correct params
        MockFailedTask.assert_called_once()
        call_kwargs = MockFailedTask.call_args[1]
        assert call_kwargs['task_type'] == 'scrape'
        assert call_kwargs['article_url'] == 'https://example.com'
        assert call_kwargs['exception_type'] == 'ValueError'
        assert call_kwargs['exception_message'] == 'Test error message'

        # Verify it was added and committed
        mock_session.add.assert_called_once_with(mock_instance)
        mock_session.commit.assert_called_once()


def test_record_failure_with_article_id():
    """record_failure should store article_id when provided"""
    with patch('src.main.FailedTask') as MockFailedTask:
        from src.main import record_failure

        mock_session = MagicMock()
        article_id = uuid.uuid4()

        record_failure(mock_session, 'analyze', None, article_id, Exception("Analysis failed"))

        call_kwargs = MockFailedTask.call_args[1]
        assert call_kwargs['task_type'] == 'analyze'
        assert call_kwargs['article_id'] == article_id

