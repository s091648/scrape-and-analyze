import pytest

from src.modules.collection.domain.value_objects.url import UrlHash
from src.modules.collection.domain.exceptions import InvalidUrlHashError


def test_from_url_generates_64_char_hash():
    h = UrlHash.from_url("https://example.com/article")
    assert len(h.value) == 64


def test_from_url_raises_for_empty_url():
    with pytest.raises(InvalidUrlHashError):
        UrlHash.from_url("")


@pytest.mark.parametrize("value", ["", "short", "a" * 63, "a" * 65])
def test_construct_raises_for_invalid_length(value):
    with pytest.raises(InvalidUrlHashError):
        UrlHash(value=value)


def test_str_returns_hash_value():
    h = UrlHash.from_url("https://example.com/article")
    assert str(h) == h.value
