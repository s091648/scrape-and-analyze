from __future__ import annotations

from chatbot_plugin_sdk.providers import EndpointProvider


class EndpointRagProvider:
    """RAG embedding provider that calls an external HTTP embedding service.

    Thin wrapper around chatbot-plugin-sdk EndpointProvider that encapsulates
    rate-limit and role-specific configuration so bootstrap stays clean.

    Implements both DenseEmbeddingProvider and SparseEmbeddingProvider protocols
    depending on ``role``; the underlying EndpointProvider handles the distinction
    via ``response_key``.
    """

    def __init__(
        self,
        url: str,
        role: str,
        api_key: str | None = None,
        dimension: int | None = None,
        rpm: int | None = None,
        tpm: int | None = None,
        rpd: int | None = None,
    ) -> None:
        rate_limit = None
        if all(v is not None for v in (rpm, tpm, rpd)):
            from chatbot_plugin_sdk.rate_limit import SlidingWindowStrategy
            rate_limit = SlidingWindowStrategy(rpm=rpm, tpm=tpm, rpd=rpd)

        response_key = 'sparse' if role == 'sparse' else 'dense'
        self._provider = EndpointProvider(
            url=url,
            response_key=response_key,
            api_key=api_key,
            dimension=dimension if role == 'dense' else None,
            rate_limit=rate_limit,
        )
        self.dimension: int = self._provider.dimension

    async def embed(self, texts: list[str]) -> list:
        return await self._provider.embed(texts)
