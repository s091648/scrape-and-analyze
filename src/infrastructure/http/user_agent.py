"""
Per-domain User-Agent pool with rotation support.

Usage:
    pool = UserAgentPool()
    ua = pool.get("example.com")     # returns a stable UA for this domain
    ua = pool.rotate("example.com")  # forces switch to next UA (call on 403)
"""
import random
import threading

_UA_POOL: list[str] = [
    # Chrome 122-124 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Firefox on Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]


class UserAgentPool:
    """Thread-safe UA pool with per-domain sticky assignment and manual rotation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # domain → current index into _UA_POOL
        self._domain_index: dict[str, int] = {}

    def get(self, domain: str | None = None) -> str:
        """
        Return the current UA for *domain*.
        If domain is None or not yet seen, assign a random starting index.
        """
        if not domain:
            return random.choice(_UA_POOL)
        with self._lock:
            if domain not in self._domain_index:
                self._domain_index[domain] = random.randint(0, len(_UA_POOL) - 1)
            return _UA_POOL[self._domain_index[domain]]

    def rotate(self, domain: str) -> str:
        """
        Advance to the next UA for *domain* and return it.
        Called by HttpClient when a 403 is received.
        """
        with self._lock:
            idx = self._domain_index.get(domain, 0)
            new_idx = (idx + 1) % len(_UA_POOL)
            self._domain_index[domain] = new_idx
            return _UA_POOL[new_idx]
