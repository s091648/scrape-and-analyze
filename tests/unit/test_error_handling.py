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


@patch('src.main.get_session')
@patch('src.main.ClaudeProvider')
@patch('src.main.load_prompt')
def test_run_remediate_retries_failed_analyses(mock_prompt, mock_provider, mock_get_session):
    """run_remediate should retry failed analysis tasks"""
    from src.main import run_remediate
    from src.models.failed_task import FailedTask
    from src.models.article import Article

    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    article_id = uuid.uuid4()
    mock_failed_task = MagicMock(spec=FailedTask)
    mock_failed_task.task_type = 'analyze'
    mock_failed_task.article_id = article_id
    mock_failed_task.resolved = False

    mock_article = MagicMock(spec=Article)
    mock_article.id = article_id
    mock_article.content = "Test content"

    mock_session.query.return_value.filter_by.return_value.all.return_value = [mock_failed_task]
    # run_remediate uses session.get() (SQLAlchemy 2.0 style)
    mock_session.get.return_value = mock_article

    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = MagicMock(
        tags=['test'],
        pain_points='',
        insights='',
        innovations='',
        input_tokens=100,
        output_tokens=50
    )
    mock_provider.return_value = mock_analyzer
    mock_prompt.return_value = "test prompt"

    with patch('src.main.has_analysis', return_value=False):
        run_remediate()

    assert mock_failed_task.resolved is True


@patch('src.main.get_session')
def test_run_remediate_skips_already_resolved(mock_get_session):
    """run_remediate should skip already resolved failures"""
    from src.main import run_remediate

    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    mock_session.query.return_value.filter_by.return_value.all.return_value = []

    run_remediate()

    mock_session.get.assert_not_called()
