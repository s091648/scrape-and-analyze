import pytest
from unittest.mock import MagicMock, patch
import sys


class TestMain:
    """Test main() function"""

    def test_main_exits_without_database_url(self, monkeypatch, capsys):
        """main() must exit when DATABASE_URL is missing"""
        from scripts.create_admin import main

        monkeypatch.delenv("DATABASE_URL", raising=False)
        with patch("builtins.input", side_effect=Exception("Should not prompt")):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 1
        out = capsys.readouterr()
        assert "DATABASE_URL" in out.err or "DATABASE_URL" in out.out

    def test_main_requires_password(self, monkeypatch, capsys):
        """main() must require password input"""
        from scripts.create_admin import main

        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        # Provide 4 inputs: username, empty password, email, name
        inputs = iter(["admin", "", "test@test.com", ""])
        with patch("builtins.input", lambda _: next(inputs)):
            with pytest.raises(SystemExit) as exc:
                main()

        assert exc.value.code == 1
        out = capsys.readouterr()
        assert "password" in out.err.lower() or "password" in out.out.lower()