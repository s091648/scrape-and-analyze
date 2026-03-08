import pytest


@pytest.fixture
def mock_session():
    from unittest.mock import MagicMock
    return MagicMock()
