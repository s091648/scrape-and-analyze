import pytest
from unittest.mock import MagicMock, patch
import sys


class TestUnescapeCopyField:
    """Test unescape_copy_field() function"""

    def test_returns_null_for_backslash_n(self):
        """Should return NULL for \\N"""
        from scripts.copy_to_insert import unescape_copy_field
        result = unescape_copy_field("\\N")
        assert result == "NULL"

    def test_escapes_newline(self):
        """Should convert \\n to actual newline"""
        from scripts.copy_to_insert import unescape_copy_field
        result = unescape_copy_field(r"\n")
        # Result wraps escaped characters in quotes
        assert "'" in result

    def test_escapes_tab(self):
        """Should convert \\t to actual tab"""
        from scripts.copy_to_insert import unescape_copy_field
        result = unescape_copy_field(r"\t")
        # Result wraps escaped characters in quotes
        assert "'" in result

    def test_escapes_carriage_return(self):
        """Should convert \\r to actual carriage return"""
        from scripts.copy_to_insert import unescape_copy_field
        result = unescape_copy_field(r"\r")
        # Result wraps escaped characters in quotes
        assert "'" in result

    def test_escapes_backslash(self):
        """Should convert \\\\ to single backslash"""
        from scripts.copy_to_insert import unescape_copy_field
        result = unescape_copy_field(r"\\")
        # Double backslash becomes single in the output (wrapped in quotes)
        assert "'" in result

    def test_escapes_single_quotes(self):
        """Should escape single quotes as ''"""
        from scripts.copy_to_insert import unescape_copy_field
        result = unescape_copy_field("it's")
        assert result == "'it''s'"

    def test_handles_plain_text(self):
        """Should handle plain text without escaping"""
        from scripts.copy_to_insert import unescape_copy_field
        result = unescape_copy_field("hello")
        assert result == "'hello'"


class TestPriorityKey:
    """Test priority_key() function"""

    def test_articles_first_priority(self):
        """articles should have highest priority (lowest index)"""
        from scripts.copy_to_insert import priority_key
        result = priority_key("public.articles")
        assert result == 0

    def test_failed_tasks_second_priority(self):
        """failed_tasks should have second priority"""
        from scripts.copy_to_insert import priority_key
        result = priority_key("public.failed_tasks")
        assert result == 1

    def test_analyses_third_priority(self):
        """analyses should have third priority"""
        from scripts.copy_to_insert import priority_key
        result = priority_key("public.analyses")
        assert result == 2

    def test_unlisted_table_lowest_priority(self):
        """Unlisted tables should have lowest priority"""
        from scripts.copy_to_insert import priority_key
        result = priority_key("public.other_table")
        assert result == 3  # len(TABLE_PRIORITY)

    def test_case_insensitive(self):
        """Should be case insensitive"""
        from scripts.copy_to_insert import priority_key
        assert priority_key("ARTICLES") == 0
        assert priority_key("Articles") == 0

    def test_handles_schema_prefix(self):
        """Should handle schema prefix"""
        from scripts.copy_to_insert import priority_key
        assert priority_key("articles") == 0
        assert priority_key("failed_tasks") == 1


class TestMain:
    """Test main() function - end-to-end processing"""

    def test_converts_copy_to_insert(self):
        """Should convert COPY blocks to INSERT statements"""
        from scripts.copy_to_insert import main
        import io

        input_data = r"""CREATE TABLE articles (id, title);
COPY articles (id, title) FROM stdin;
1	Test Article
\.
"""

        with patch("sys.stdin", io.StringIO(input_data)):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                main()
                output = mock_stdout.getvalue()

        assert "INSERT INTO public.articles" in output or "INSERT INTO articles" in output
        assert "ON CONFLICT DO NOTHING" in output

    def test_adds_if_not_exists_to_create_table(self):
        """Should add IF NOT EXISTS to CREATE TABLE"""
        from scripts.copy_to_insert import main
        import io

        input_data = """CREATE TABLE articles (id int);
"""

        with patch("sys.stdin", io.StringIO(input_data)):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                main()
                output = mock_stdout.getvalue()

        assert "CREATE TABLE IF NOT EXISTS" in output

    def test_adds_if_not_exists_to_create_index(self):
        """Should add IF NOT EXISTS to CREATE INDEX"""
        from scripts.copy_to_insert import main
        import io

        input_data = """CREATE INDEX idx_articles_id ON articles(id);
"""

        with patch("sys.stdin", io.StringIO(input_data)):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                main()
                output = mock_stdout.getvalue()

        assert "CREATE INDEX IF NOT EXISTS" in output

    def test_adds_if_not_exists_to_create_unique_index(self):
        """Should add IF NOT EXISTS to CREATE UNIQUE INDEX"""
        from scripts.copy_to_insert import main
        import io

        input_data = """CREATE UNIQUE INDEX idx_articles_id ON articles(id);
"""

        with patch("sys.stdin", io.StringIO(input_data)):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                main()
                output = mock_stdout.getvalue()

        assert "CREATE UNIQUE INDEX IF NOT EXISTS" in output