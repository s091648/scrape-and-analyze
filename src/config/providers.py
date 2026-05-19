"""
Provider configuration loader — reads providers.toml only.
No database imports, no side effects.
"""
import os
import tomllib
from typing import Any, Dict, List


def load_providers(path: str = None) -> List[Dict[str, Any]]:
    """Load provider definitions from providers.toml, sorted by priority."""
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "providers.toml",
        )
    with open(path, "rb") as f:
        data = tomllib.load(f)
    providers = data.get("providers", [])
    return sorted(providers, key=lambda p: p["priority"])


def load_tag_normalization_config(path: str = None) -> dict:
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "providers.toml",
        )
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("tag_normalization", {
        "auto_merge_threshold": 0.92,
        "suggest_threshold": 0.85,
        "embedding_model": "text-embedding-004",
        "api_key_env": "GEMINI_API_KEY",
    })
