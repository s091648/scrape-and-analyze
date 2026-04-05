import os
from typing import Optional


def get_proxies() -> Optional[dict]:
    """Return a proxies dict for requests if FIXIE_URL is set, else None."""
    fixie_url = os.environ.get("FIXIE_URL")
    if fixie_url:
        return {"http": fixie_url, "https": fixie_url}
    return None
