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
         patch('src.main.build_analyzer'), \
         patch('src.main.load_prompt', return_value='prompt'):
        mock_arxiv.return_value.scrape.return_value = []

        from src.main import run_daily_scrape
        run_daily_scrape(time.time())

    assert mock_rss_scraper.called


@patch('src.main.LLM_MODEL', 'test-model')
def test_analyze_article_writes_tags():
    """analyze_article should upsert tags and link them to the article"""
    from src.main import analyze_article
    from src.analyzers import AnalysisResult

    session = MagicMock()
    article = MagicMock()
    article.id = 'test-article-id'
    article.content = 'content'
    article.tags = []

    mock_result = AnalysisResult(
        tag_groups=[{"group": "digital_twin", "tags": ["virtual replica"]}],
        pain_points='p', insights='i', innovations='n',
        input_tokens=10, output_tokens=5,
    )
    analyzer = MagicMock()
    analyzer.analyze.return_value = mock_result

    # Tag query returns None (new tag to be created)
    session.query.return_value.filter_by.return_value.first.return_value = None

    import uuid
    result = analyze_article(session, article, analyzer, 'prompt', str(uuid.uuid4()))

    assert result is True
    session.add.assert_called()


def test_build_analyzer_returns_provider_chain():
    from unittest.mock import patch, MagicMock

    mock_providers = [
        {
            'name': 'gemini', 'priority': 1, 'model': 'gemini-2.0-flash',
            'api_key_env': 'GEMINI_API_KEY',
            'strategy': {'type': 'leaky_bucket', 'rpm': 5, 'tpm': 250000, 'rpd': 20}
        }
    ]

    with patch('src.main.load_providers', return_value=mock_providers), \
         patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}), \
         patch('src.main.GeminiProvider') as mock_gemini:

        mock_gemini.return_value = MagicMock()

        from src.main import build_analyzer
        from src.analyzers.provider_chain import ProviderChain
        result = build_analyzer()

    assert isinstance(result, ProviderChain)


def test_build_analyzer_noop_strategy_for_unknown_type():
    from unittest.mock import patch, MagicMock

    mock_providers = [
        {
            'name': 'openrouter', 'priority': 1, 'model': 'deepseek/deepseek-chat',
            'api_key_env': 'OPENROUTER_API_KEY',
            'strategy': {'type': 'noop'}
        }
    ]

    with patch('src.main.load_providers', return_value=mock_providers), \
         patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-key'}), \
         patch('src.main.OpenRouterProvider') as mock_or:

        mock_or.return_value = MagicMock()

        from src.main import build_analyzer
        result = build_analyzer()

    assert result is not None


def test_prepare_content_for_analysis_uses_sections_for_arxiv():
    from unittest.mock import MagicMock
    from src.scrapers.content_parsers import prepare_content_for_analysis

    article = MagicMock()
    article.source = 'arxiv'
    article.content = "Abstract\nReal abstract.\n\n1 Introduction\nIntro text."
    article.metadata_ = {'abstract': 'Short abstract.'}

    result = prepare_content_for_analysis(article)
    # Should use sections, not the short fallback abstract
    assert 'Real abstract' in result or 'Intro text' in result


def test_prepare_content_for_analysis_falls_back_to_metadata_abstract():
    from unittest.mock import MagicMock
    from src.scrapers.content_parsers import prepare_content_for_analysis

    article = MagicMock()
    article.source = 'arxiv'
    article.content = 'No headings here at all just plain text.'
    article.metadata_ = {'abstract': 'The stored abstract.'}

    result = prepare_content_for_analysis(article)
    assert result == 'The stored abstract.'


def test_prepare_content_for_analysis_passthrough_for_non_arxiv():
    from unittest.mock import MagicMock
    from src.scrapers.content_parsers import prepare_content_for_analysis

    article = MagicMock()
    article.source = 'techcrunch'
    article.content = 'Blog article content.'
    article.metadata_ = {}

    result = prepare_content_for_analysis(article)
    assert result == 'Blog article content.'


def test_analyze_article_uses_prepare_content_for_analysis(mock_session):
    """analyze_article should call prepare_content_for_analysis before the LLM."""
    from unittest.mock import MagicMock, patch
    from src.main import analyze_article

    article = MagicMock()
    article.source = 'arxiv'
    article.content = 'Full PDF text.'
    article.metadata_ = {'abstract': 'Short abstract.'}
    article.id = 'uuid-1'
    article.tags = []

    analyzer = MagicMock()
    analyzer.analyze.return_value = MagicMock(
        pain_points=[], insights=[], innovations=[],
        tag_groups=[], input_tokens=10, output_tokens=20,
    )

    with patch('src.main.prepare_content_for_analysis', return_value='prepared content') as mock_prep:
        analyze_article(mock_session, article, analyzer, 'prompt', 'corr-id')
        mock_prep.assert_called_once_with(article)
        analyzer.analyze.assert_called_once_with('prepared content', 'prompt')
