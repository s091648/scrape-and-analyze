from enum import Enum


class RateLimitKind(Enum):
    """Classification of a rate-limit-shaped error a provider can report via
    BaseProvider._classify_rate_limit(). RPM/TPM windows clear within seconds —
    BaseProvider retries those with backoff. RPD means "this provider is done
    for the rest of this run" — BaseProvider skips retrying and escalates
    straight to RateLimitExhausted instead of burning the retry budget on a
    doomed call."""
    RPM = "rpm"
    TPM = "tpm"
    RPD = "rpd"
