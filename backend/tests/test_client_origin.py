"""Unit tests for backend/rate_limit/client_origin.py — 026-rate-limit-codegen
CodeRabbit review: get_client_origin must trust only the rightmost
TRUSTED_PROXY_HOPS hop(s) of X-Forwarded-For (appended by our own reverse
proxy), never client-supplied leftmost hops, or a caller can spoof its way
around origin-keyed rate limits."""
import importlib
import os
from unittest.mock import patch

from fastapi import Request


def _reload_client_origin():
    import backend.config as config
    importlib.reload(config)
    import backend.rate_limit.client_origin as m
    importlib.reload(m)
    return m


def _make_request(client_host="1.2.3.4", forwarded_for=None):
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    scope = {"type": "http", "headers": headers, "client": (client_host, 12345)}
    return Request(scope)


def test_no_forwarded_header_uses_socket_peer():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TRUSTED_PROXY_HOPS", None)
        m = _reload_client_origin()
        request = _make_request(client_host="1.2.3.4")
        assert m.get_client_origin(request) == "1.2.3.4"


def test_single_forwarded_hop_is_trusted():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TRUSTED_PROXY_HOPS", None)
        m = _reload_client_origin()
        request = _make_request(client_host="10.0.0.1", forwarded_for="1.2.3.4")
        assert m.get_client_origin(request) == "1.2.3.4"


def test_leftmost_client_supplied_hop_is_never_trusted():
    """A caller can put anything in the leftmost X-Forwarded-For entry — only the
    rightmost entry (appended by our own trusted proxy) may be trusted, or a
    caller could set an arbitrary origin and bypass origin-keyed rate limits."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TRUSTED_PROXY_HOPS", None)
        m = _reload_client_origin()
        request = _make_request(
            client_host="10.0.0.1",
            forwarded_for="attacker-spoofed-value, 9.9.9.9",
        )
        assert m.get_client_origin(request) == "9.9.9.9"


def test_trusted_proxy_hops_zero_ignores_forwarded_header():
    with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "0"}):
        m = _reload_client_origin()
        request = _make_request(client_host="10.0.0.1", forwarded_for="9.9.9.9, 1.2.3.4")
        assert m.get_client_origin(request) == "10.0.0.1"


def test_trusted_proxy_hops_two_reads_second_from_right():
    with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "2"}):
        m = _reload_client_origin()
        request = _make_request(forwarded_for="attacker, 9.9.9.9, 1.2.3.4")
        assert m.get_client_origin(request) == "9.9.9.9"


def test_fewer_hops_than_trusted_proxy_hops_falls_back_to_socket_peer():
    with patch.dict(os.environ, {"TRUSTED_PROXY_HOPS": "2"}):
        m = _reload_client_origin()
        request = _make_request(client_host="10.0.0.1", forwarded_for="1.2.3.4")
        assert m.get_client_origin(request) == "10.0.0.1"


def test_no_client_and_no_forwarded_header_returns_none():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TRUSTED_PROXY_HOPS", None)
        m = _reload_client_origin()
        scope = {"type": "http", "headers": [], "client": None}
        assert m.get_client_origin(Request(scope)) is None
