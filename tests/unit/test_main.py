import pytest
from unittest.mock import patch, MagicMock


def test_parse_args_accepts_daily():
    """parse_args should accept 'daily' command"""
    from src.main import parse_args

    args = parse_args(['daily'])
    assert args.command == 'daily'


def test_parse_args_accepts_weekly():
    """parse_args should accept 'weekly' command"""
    from src.main import parse_args

    args = parse_args(['weekly'])
    assert args.command == 'weekly'


def test_parse_args_accepts_remediate():
    """parse_args should accept 'remediate' command"""
    from src.main import parse_args

    args = parse_args(['remediate'])
    assert args.command == 'remediate'


def test_parse_args_rejects_invalid_command():
    """parse_args should reject invalid commands"""
    from src.main import parse_args

    with pytest.raises(SystemExit):
        parse_args(['invalid'])


def test_check_timeout_returns_true_when_exceeded():
    """check_timeout should return True when max time exceeded"""
    from src.main import check_timeout, MAX_EXECUTION_TIME
    import time

    start_time = time.time() - MAX_EXECUTION_TIME - 1
    assert check_timeout(start_time) is True


def test_check_timeout_returns_false_when_not_exceeded():
    """check_timeout should return False when within time limit"""
    from src.main import check_timeout
    import time

    start_time = time.time()
    assert check_timeout(start_time) is False


@patch('src.main.get_session')
@patch('src.main.RssScraper')
def test_run_daily_scrape_uses_rss_sources(mock_rss_scraper, mock_get_session):
    """run_daily_scrape should use RSS sources"""
    import time

    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    mock_scraper_instance = MagicMock()
    mock_scraper_instance.scrape.return_value = []
    mock_rss_scraper.return_value = mock_scraper_instance

    with patch('src.main.ArxivScraper') as mock_arxiv, \
         patch('src.main.ClaudeProvider'), \
         patch('src.main.load_prompt', return_value='prompt'):
        mock_arxiv.return_value.scrape.return_value = []

        from src.main import run_daily_scrape
        run_daily_scrape(time.time())

    assert mock_rss_scraper.called
