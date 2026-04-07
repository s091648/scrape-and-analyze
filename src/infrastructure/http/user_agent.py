"""
Per-domain User-Agent pool with rotation support and browser-header mimicry.

Usage:
    pool = UserAgentPool()
    ua = pool.get("example.com")              # returns a stable UA for this domain
    ua = pool.rotate("example.com")           # forces switch to next UA (call on 403)
    hdrs = get_browser_headers(ua)            # full Chrome/Firefox/Safari header set
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


def _detect_platform(ua: str) -> str:
    if "Windows" in ua:
        return "Windows"
    if "Macintosh" in ua or "Mac OS X" in ua:
        return "macOS"
    return "Linux"


def _chrome_version(ua: str) -> str | None:
    """Extract major version from Chrome/Chromium UA string."""
    import re
    m = re.search(r"Chrome/(\d+)", ua)
    return m.group(1) if m else None


def _edge_version(ua: str) -> str | None:
    import re
    m = re.search(r"Edg/(\d+)", ua)
    return m.group(1) if m else None


def get_browser_headers(ua: str, referer: str | None = None) -> dict:
    """
    Return a complete set of browser-like request headers for *ua*.

    These complement the User-Agent and are required to pass basic
    bot-detection checks (Cloudflare, Akamai Bot Manager, etc.) that
    inspect the full header fingerprint.

    Only sets headers that match the UA's actual browser — Firefox and
    Safari do NOT send sec-ch-ua, so we omit those to avoid mismatches
    that are themselves a detection signal.
    """
    platform = _detect_platform(ua)
    is_mobile = "Mobile" in ua or "Android" in ua

    base = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;"
            "q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
    }

    if referer:
        base["Referer"] = referer

    edge_ver = _edge_version(ua)
    chrome_ver = _chrome_version(ua)

    if edge_ver:
        # Edge — Chromium-based, sends sec-ch-ua with Edge brand
        base.update({
            "sec-ch-ua": (
                f'"Chromium";v="{edge_ver}", '
                f'"Microsoft Edge";v="{edge_ver}", '
                '"Not-A.Brand";v="99"'
            ),
            "sec-ch-ua-mobile": "?1" if is_mobile else "?0",
            "sec-ch-ua-platform": f'"{platform}"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none" if not referer else "same-origin",
            "Sec-Fetch-User": "?1",
        })
    elif chrome_ver:
        # Chrome — sends sec-ch-ua
        base.update({
            "sec-ch-ua": (
                f'"Chromium";v="{chrome_ver}", '
                f'"Google Chrome";v="{chrome_ver}", '
                '"Not-A.Brand";v="99"'
            ),
            "sec-ch-ua-mobile": "?1" if is_mobile else "?0",
            "sec-ch-ua-platform": f'"{platform}"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none" if not referer else "same-origin",
            "Sec-Fetch-User": "?1",
        })
    elif "Firefox" in ua:
        # Firefox — does NOT send sec-ch-ua; sends DNT
        base["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        )
        base["DNT"] = "1"
    # Safari omits sec-ch-ua too; no extra headers needed beyond base

    return base


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
