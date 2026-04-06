"""
UrlHash value object — immutable, self-validating.

Encapsulates the SHA-256 URL hashing logic that was previously scattered
between src/utils/sanitizer.py (generate_url_hash) and direct call sites.

Usage:
    h = UrlHash.from_url("https://example.com/article")
    h.value   # "e3b0c44..."
"""
import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class UrlHash:
    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) != 64:
            raise ValueError(f"UrlHash must be a 64-char hex string, got: {self.value!r}")

    @classmethod
    def from_url(cls, url: str) -> "UrlHash":
        """Compute SHA-256 of *url* and return a UrlHash instance."""
        if not url:
            raise ValueError("Cannot create UrlHash from empty URL")
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return cls(value=digest)

    def __str__(self) -> str:
        return self.value
