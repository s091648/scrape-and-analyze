from typing import Optional

from src.config.settings import FIXIE_URL


def get_proxies() -> Optional[dict]:
    """Return a proxies dict for requests if FIXIE_URL is set, else None."""
    if FIXIE_URL:
        return {"http": FIXIE_URL, "https": FIXIE_URL}
    return None
