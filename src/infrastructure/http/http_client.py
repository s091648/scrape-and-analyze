"""
Unified HTTP client — composes proxy + UA rotation + per-domain rate limiting + retry.

Typical usage (after main.py calls init_default_client):

    from src.infrastructure.http.http_client import get_default_client
    response = get_default_client().get(url)

The returned Response always has a 2xx status code; non-retryable errors are
raised as exceptions (HTTPError, ConnectionError, etc.) for callers to handle.
"""
from __future__ import annotations

import random
import time
import requests
from typing import Optional
from urllib.parse import urlparse

from src.infrastructure.http.rate_limiter import DomainRateLimiter
from src.infrastructure.http.retry import make_retry_policy
from src.infrastructure.http.user_agent import UserAgentPool, get_browser_headers
from src.utils.logging import get_logger
from src.utils.proxy import get_proxies

logger = get_logger(__name__)


def _extract_domain(url: str) -> str:
    return urlparse(url).netloc


class HttpClient:
    """
    Thread-safe HTTP client.

    Flow for each GET:
      1. Acquire a rate-limit token for the request's domain (may block).
      2. Pick the current User-Agent for that domain.
      3. Build a full browser-like header set (sec-ch-ua, Sec-Fetch-*, etc.).
      4. Send the request through the tenacity retry policy (handles 429 / 5xx).
      5. On 403: wait with jitter, rotate to next UA, retry up to *max_403_rotations* times.
      6. Return the successful Response (2xx), or raise the last exception.

    Args:
        rate_limiter:            Per-domain token-bucket limiter.
        ua_pool:                 Rotating browser UA pool.
        proxies:                 ``requests``-style proxies dict (e.g. from Fixie).
        max_403_rotations:       How many times to rotate UA before giving up on 403.
        retry_max_attempts:      Max retry attempts for 429/5xx/network errors.
        rotation_delay_base:     Base seconds to wait between 403 UA rotations.
                                 Actual wait = uniform(base, base * 2) for jitter.
    """

    def __init__(
        self,
        rate_limiter: DomainRateLimiter,
        ua_pool: UserAgentPool,
        proxies: Optional[dict] = None,
        proxy_enabled: bool = False,
        max_403_rotations: int = 2,
        retry_max_attempts: int = 4,
        rotation_delay_base: float = 3.0,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._ua_pool = ua_pool
        self._proxies = proxies
        self._proxy_enabled = proxy_enabled
        self._max_403_rotations = max_403_rotations
        self._rotation_delay_base = rotation_delay_base
        self._retry_policy = make_retry_policy(max_attempts=retry_max_attempts)

    def get(self, url: str, timeout: int = 30, **kwargs) -> requests.Response:
        """
        Perform an HTTP GET, applying rate limit → UA selection → retry policy.

        *kwargs* are forwarded to ``requests.get`` (e.g. ``params``, ``stream``).
        A ``headers`` kwarg will be merged with the managed User-Agent header.
        """
        domain = _extract_domain(url)

        caller_headers: dict = kwargs.pop("headers", {})

        last_403_exc: Optional[Exception] = None
        for rotation in range(self._max_403_rotations + 1):
            # Dynamically decide whether to use proxy based on current state
            proxies = self._proxies if self._proxy_enabled else None
            ua = self._ua_pool.get(domain)
            # Full browser-like header fingerprint — reduces bot-detection triggers
            headers = {
                "User-Agent": ua,
                **get_browser_headers(ua),
                **caller_headers,  # caller overrides last
            }
            try:
                # connection() enforces rate limiting + single-connection for arXiv domains
                with self._rate_limiter.connection(domain):
                    for attempt in self._retry_policy:
                        with attempt:
                            resp = requests.get(
                                url,
                                headers=headers,
                                proxies=proxies,
                                timeout=timeout,
                                **kwargs,
                            )
                            resp.raise_for_status()
                return resp
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None:
                    status_code = exc.response.status_code
                    if status_code == 407 and proxies is not None:
                        logger.warning(
                            "http_407_proxy_authentication_required",
                            url=url,
                            retry_without_proxy=True,
                        )
                        self._proxy_enabled = False
                        continue
                    if status_code == 403:
                        if rotation < self._max_403_rotations:
                            # Jitter delay before next rotation so the burst
                            # doesn't look like a bot to the server
                            jitter = random.uniform(
                                self._rotation_delay_base,
                                self._rotation_delay_base * 2,
                            )
                            logger.warning(
                                "http_403_rotating_ua",
                                url=url,
                                rotation=rotation + 1,
                                max_rotations=self._max_403_rotations,
                                retry_after_seconds=round(jitter, 1),
                            )
                            time.sleep(jitter)
                            self._ua_pool.rotate(domain)
                        last_403_exc = exc
                        continue
                raise

        logger.error("http_403_exhausted", url=url)
        raise last_403_exc  # type: ignore[misc]

    @classmethod
    def build_default(cls) -> "HttpClient":
        """Construct an HttpClient with production defaults (proxy from env)."""
        proxies = get_proxies()
        proxy_enabled = True if proxies else False

        return cls(
            rate_limiter=DomainRateLimiter(),
            ua_pool=UserAgentPool(),
            proxies=proxies,
            proxy_enabled=proxy_enabled,
        )


# ── Module-level singleton ────────────────────────────────────────────────────
# Initialised by main.py via init_default_client() before any scraper runs.

_default_client: Optional[HttpClient] = None


def init_default_client(client: HttpClient) -> None:
    """Called once at startup (in main.py) to set the shared client."""
    global _default_client
    _default_client = client


def get_default_client() -> HttpClient:
    """Return the shared client, creating a default one if not yet initialised."""
    global _default_client
    if _default_client is None:
        logger.warning("http_client_not_initialised_using_default")
        _default_client = HttpClient.build_default()
    return _default_client
