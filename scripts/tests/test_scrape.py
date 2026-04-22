import pytest
from unittest.mock import MagicMock, patch
import sys


class TestParseArgs:
    """Test parse_args() function"""

    def test_parse_args_requires_source(self):
        """parse_args should require --source argument"""
        from scripts.scrape import parse_args

        with patch.object(sys, "argv", ["scrape.py"]):
            with pytest.raises(SystemExit):
                parse_args()

    def test_parse_args_accepts_rss_source(self):
        """parse_args should accept rss as valid source"""
        from scripts.scrape import parse_args

        with patch.object(sys, "argv", ["scrape.py", "--source", "rss"]):
            args = parse_args()
            assert args.source == "rss"

    def test_parse_args_accepts_blog_source(self):
        """parse_args should accept blog as valid source"""
        from scripts.scrape import parse_args

        with patch.object(sys, "argv", ["scrape.py", "--source", "blog"]):
            args = parse_args()
            assert args.source == "blog"

    def test_parse_args_accepts_arxiv_source(self):
        """parse_args should accept arxiv as valid source"""
        from scripts.scrape import parse_args

        with patch.object(sys, "argv", ["scrape.py", "--source", "arxiv"]):
            args = parse_args()
            assert args.source == "arxiv"

    def test_parse_args_rejects_invalid_source(self):
        """parse_args should reject invalid source types"""
        from scripts.scrape import parse_args

        with patch.object(sys, "argv", ["scrape.py", "--source", "invalid"]):
            with pytest.raises(SystemExit):
                parse_args()

    def test_parse_args_no_analyze_flag(self):
        """parse_args should set no_analyze flag correctly"""
        from scripts.scrape import parse_args

        with patch.object(sys, "argv", ["scrape.py", "--source", "rss", "--no-analyze"]):
            args = parse_args()
            assert args.no_analyze is True

    def test_parse_args_default_no_analyze_false(self):
        """parse_args should default no_analyze to False"""
        from scripts.scrape import parse_args

        with patch.object(sys, "argv", ["scrape.py", "--source", "rss"]):
            args = parse_args()
            assert args.no_analyze is False

    def test_parse_args_accepts_limit(self):
        """parse_args should accept --limit argument"""
        from scripts.scrape import parse_args

        with patch.object(sys, "argv", ["scrape.py", "--source", "rss", "--limit", "10"]):
            args = parse_args()
            assert args.limit == 10


class TestGetActiveSettingsByType:
    """Test _get_active_settings_by_type() function"""

    def test_returns_empty_list_when_no_settings(self):
        """Should return empty list when no active settings found"""
        from scripts.scrape import _get_active_settings_by_type

        session = MagicMock()
        session.query.return_value.filter_by.return_value.all.return_value = []

        result = _get_active_settings_by_type(session, "rss")

        assert result == []

    def test_converts_db_rows_to_domain_entities(self):
        """Should convert database rows to ScraperSetting domain entities"""
        from scripts.scrape import _get_active_settings_by_type
        from src.modules.collection.domain.entities import ScraperSetting

        session = MagicMock()
        mock_row = MagicMock()
        mock_row.id = "setting-id"
        mock_row.name = "test-source"
        mock_row.source_type = "rss"
        mock_row.url = "http://example.com/feed"
        mock_row.frequency = 24
        mock_row.topic_id = None
        mock_row.selector_config = None
        mock_row.last_scraped_at = None
        mock_row.is_active = True

        session.query.return_value.filter_by.return_value.all.return_value = [mock_row]

        result = _get_active_settings_by_type(session, "rss")

        assert len(result) == 1
        assert isinstance(result[0], ScraperSetting)
        assert result[0].source == "test-source"
        assert result[0].source_type == "rss"

    def test_uses_topic_prompt_override(self):
        """Should use topic's prompt_override when topic_id is set"""
        from scripts.scrape import _get_active_settings_by_type

        session = MagicMock()

        mock_row = MagicMock()
        mock_row.id = "setting-id"
        mock_row.name = "test-source"
        mock_row.source_type = "rss"
        mock_row.url = "http://example.com/feed"
        mock_row.frequency = 24
        mock_row.topic_id = "topic-uuid"
        mock_row.selector_config = None
        mock_row.last_scraped_at = None
        mock_row.is_active = True

        mock_topic = MagicMock()
        mock_topic.prompt_override = "custom prompt"

        session.query.return_value.filter_by.return_value.all.return_value = [mock_row]
        session.query.return_value.filter_by.return_value.first.return_value = mock_topic

        result = _get_active_settings_by_type(session, "rss")

        assert result[0].prompt_override == "custom prompt"


class TestMain:
    """Test main() function"""

    def test_main_exits_without_database_url(self, monkeypatch, capsys):
        """main() must exit(1) when DATABASE_URL is missing"""
        import sys
        from scripts.scrape import main

        monkeypatch.setattr(sys, "argv", ["scrape.py", "--source", "rss"])
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert "DATABASE_URL" in capsys.readouterr().err

    def test_main_exits_when_no_active_sources(self, monkeypatch, capsys):
        """main() should exit when no active sources found"""
        import sys
        from scripts.scrape import main

        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        monkeypatch.setattr(sys, "argv", ["scrape.py", "--source", "rss"])

        with patch("scripts.scrape.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter_by.return_value.all.return_value = []
            mock_get_session.return_value = mock_session

            with patch("scripts.scrape.init_db"):
                main()

        assert "No active" in capsys.readouterr().out