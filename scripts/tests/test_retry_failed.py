import pytest
from unittest.mock import MagicMock, patch
import sys


class TestParseArgs:
    """Test parse_args() function"""

    def test_parse_args_defaults(self):
        """parse_args should have correct defaults"""
        from scripts.retry_failed import parse_args

        with patch.object(sys, "argv", ["retry_failed.py"]):
            args = parse_args()
            assert args.hours is None
            assert args.limit is None
            assert args.dry_run is False

    def test_parse_args_accepts_hours(self):
        """parse_args should accept --hours argument"""
        from scripts.retry_failed import parse_args

        with patch.object(sys, "argv", ["retry_failed.py", "--hours", "24"]):
            args = parse_args()
            assert args.hours == 24

    def test_parse_args_accepts_limit(self):
        """parse_args should accept --limit argument"""
        from scripts.retry_failed import parse_args

        with patch.object(sys, "argv", ["retry_failed.py", "--limit", "10"]):
            args = parse_args()
            assert args.limit == 10

    def test_parse_args_accepts_dry_run(self):
        """parse_args should accept --dry-run flag"""
        from scripts.retry_failed import parse_args

        with patch.object(sys, "argv", ["retry_failed.py", "--dry-run"]):
            args = parse_args()
            assert args.dry_run is True


class TestBuildArticleEntity:
    """Test _build_article_entity() function"""

    def test_converts_row_to_article_entity(self):
        """Should convert database row to Article domain entity"""
        from scripts.retry_failed import _build_article_entity
        from src.shared.domain.entities import Article
        from datetime import datetime

        mock_row = MagicMock()
        mock_row.id = "article-id"
        mock_row.url = "http://example.com"
        mock_row.url_hash = "abc123"
        mock_row.source = "rss"
        mock_row.title = "Test Article"
        mock_row.content = "Test content"
        mock_row.published_at = datetime(2024, 1, 1)
        mock_row.scraped_at = datetime(2024, 1, 2)
        mock_row.metadata_ = {"key": "value"}
        mock_row.topic_id = "topic-id"

        result = _build_article_entity(mock_row)

        assert isinstance(result, Article)
        assert result.id == "article-id"
        assert result.url == "http://example.com"
        assert result.title == "Test Article"
        assert result.metadata == {"key": "value"}

    def test_handles_missing_topic_id(self):
        """Should handle row without topic_id attribute"""
        from scripts.retry_failed import _build_article_entity
        from src.shared.domain.entities import Article

        mock_row = MagicMock()
        mock_row.id = "article-id"
        mock_row.url = "http://example.com"
        mock_row.url_hash = "abc123"
        mock_row.source = "rss"
        mock_row.title = "Test Article"
        mock_row.content = "Test content"
        mock_row.published_at = None
        mock_row.scraped_at = None
        mock_row.metadata_ = None
        # Simulate no topic_id attribute
        del mock_row.topic_id

        result = _build_article_entity(mock_row)

        assert result.topic_id is None


class TestMarkResolved:
    """Test mark_resolved() function"""

    def test_sets_resolved_flag(self):
        """Should set resolved=True and resolved_at timestamp"""
        from scripts.retry_failed import mark_resolved

        session = MagicMock()
        failure = MagicMock()
        failure.resolved = False
        failure.resolved_at = None

        mark_resolved(session, failure)

        assert failure.resolved is True
        assert failure.resolved_at is not None
        session.commit.assert_called_once()


class TestMain:
    """Test main() function"""

    def test_main_exits_without_database_url(self, monkeypatch, capsys):
        """main() must exit(1) when DATABASE_URL is missing"""
        import sys
        from scripts.retry_failed import main

        monkeypatch.setattr(sys, "argv", ["retry_failed.py"])
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert "DATABASE_URL" in capsys.readouterr().err

    def test_main_reports_no_failures(self, monkeypatch, capsys):
        """main() should report when no failures found"""
        import sys
        from scripts.retry_failed import main
        from models.failed_task import FailedTask

        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        monkeypatch.setattr(sys, "argv", ["retry_failed.py"])

        with patch("scripts.retry_failed.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter_by.return_value.all.return_value = []
            mock_get_session.return_value = mock_session

            with patch("scripts.retry_failed.init_db"):
                with patch("src.bootstrap.build_llm_service"):
                    main()

        assert "No unresolved failures" in capsys.readouterr().out

    def test_main_uses_hours_filter(self, monkeypatch, capsys):
        """main() should filter by hours when provided"""
        import sys
        from scripts.retry_failed import main

        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        monkeypatch.setattr(sys, "argv", ["retry_failed.py", "--hours", "24"])

        with patch("scripts.retry_failed.get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_session.query.return_value.filter_by.return_value.all.return_value = []
            mock_get_session.return_value = mock_session

            with patch("scripts.retry_failed.SqlAlchemyFailedTaskRepository") as mock_repo_cls:
                mock_repo = MagicMock()
                mock_repo.find_recent_failures.return_value = []
                mock_repo_cls.return_value = mock_repo

                mock_session.close = MagicMock()

                with patch("scripts.retry_failed.init_db"):
                    with patch("src.bootstrap.build_llm_service"):
                        main()

        mock_repo.find_recent_failures.assert_called_once()
        assert mock_repo.find_recent_failures.call_args[1]["hours"] == 24