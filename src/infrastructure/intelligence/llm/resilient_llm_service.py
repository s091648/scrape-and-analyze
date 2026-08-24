from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService, EmbeddingService, TextGenerationService
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.infrastructure.intelligence.llm.embedding import BaseEmbeddingProvider
from src.infrastructure.intelligence.llm.providers import BaseProvider
from src.infrastructure.intelligence.llm.rate_limit import (
    QuotaStrategy, RateLimitExhausted, ProviderSelector, PriorityFirstProviderSelector,
)
from src.infrastructure.shared.rate_limit_tracker import RateLimitedProviderTracker

logger = get_logger(__name__)


@dataclass
class ProviderHandler:
    """Pairs a provider with its quota management strategy."""
    provider: BaseProvider
    strategy: QuotaStrategy
    priority: int
    name: str

    def analyze(
        self,
        content: str,
        prompt: str,
    ) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        """Acquire quota, delegate to the provider's analyze, and record actual token usage."""
        self.strategy.acquire(estimated_tokens=len(content) // 4)
        result = self.provider.analyze(content, prompt)
        if result is not None:
            _, metadata = result
            self.strategy.record_usage(metadata.input_tokens + metadata.output_tokens)
        return result

    def translate(
        self,
        content: str,
        prompt: str,
    ) -> Optional[str]:
        """Acquire quota, delegate to the provider's translate, and record estimated token usage."""
        self.strategy.acquire(estimated_tokens=len(content) // 4)
        result = self.provider.translate(content, prompt)
        if result is not None:
            self.strategy.record_usage(len(content) // 4 + len(result) // 4)
        return result

    def generate(
        self,
        prompt: str,
    ) -> Optional[str]:
        """Acquire quota, delegate to the provider's generate, and record estimated token usage."""
        self.strategy.acquire(estimated_tokens=len(prompt) // 4)
        result = self.provider.generate(prompt)
        if result is not None:
            self.strategy.record_usage(len(prompt) // 4 + len(result) // 4)
        return result

###
### Single-thread for-now.
### Would need to add locking in handlers when moving rate-limited providers
### to the end of the list to avoid race conditions.
###
class ResilientLLMService(LLMService, TextGenerationService):
    """
    Composite LLMService that walks an ordered list of ProviderHandlers.
    Falls back to the next provider on rate limit or failure.
    """

    def __init__(self, handlers: List[ProviderHandler]) -> None:
        self._handlers = sorted(handlers, key=lambda h: h.priority)
        self._rate_limit_tracker = RateLimitedProviderTracker()

    @property
    def exhausted_providers(self) -> List[str]:
        """provider names that raised RateLimitExhausted at least once this run —
        surfaced so callers (main.py, weekly_report.py) can report it in their
        completion notification instead of a rate-limited run looking identical
        to one where every provider just happened to return None."""
        return self._rate_limit_tracker.exhausted

    def analyze(
        self,
        content: str,
        prompt: str,
    ) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        """Try each provider handler in priority order, falling back on rate-limit or failure."""

        handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            try:
                result = handler.analyze(content, prompt)

                if result is not None:
                    return result

                logger.warning(
                    "provider_returned_none",
                    provider=handler.name,
                )

            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning(
                    "provider_daily_limit_reached",
                    provider=handler.name,
                )

                self._handlers.remove(handler)
                self._handlers.append(handler)

                logger.warning(
                    "provider_moved_to_end",
                    provider=handler.name,
                )

            except Exception as e:
                logger.error(
                    "provider_failed",
                    provider=handler.name,
                    error=str(e),
                )

        logger.error("all_providers_exhausted")
        return None

    def translate(
        self,
        content: str,
        prompt: str,
    ) -> Optional[str]:
        """Try each provider handler in priority order for translation, falling back on failure."""

        handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            try:
                result = handler.translate(content, prompt)

                if result is not None:
                    return result

                logger.warning(
                    "provider_translate_returned_none",
                    provider=handler.name,
                )

            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning(
                    "provider_daily_limit_reached",
                    provider=handler.name,
                )

                self._handlers.remove(handler)
                self._handlers.append(handler)

                logger.warning(
                    "provider_moved_to_end",
                    provider=handler.name,
                )

            except Exception as e:
                logger.error(
                    "provider_translate_failed",
                    provider=handler.name,
                    error=str(e),
                )

        logger.error("all_providers_exhausted_translate")
        return None

    def generate(
        self,
        prompt: str,
    ) -> Optional[str]:
        """Try each provider handler in priority order for one-shot generation, falling back on failure."""

        handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            try:
                result = handler.generate(prompt)

                if result is not None:
                    return result

                logger.warning(
                    "provider_generate_returned_none",
                    provider=handler.name,
                )

            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning(
                    "provider_daily_limit_reached",
                    provider=handler.name,
                )

                self._handlers.remove(handler)
                self._handlers.append(handler)

                logger.warning(
                    "provider_moved_to_end",
                    provider=handler.name,
                )

            except Exception as e:
                logger.error(
                    "provider_generate_failed",
                    provider=handler.name,
                    error=str(e),
                )

        logger.error("all_providers_exhausted_generate")
        return None


@dataclass
class EmbeddingProviderHandler:
    """
    Wraps any EmbeddingService with quota management — mirrors the
    acquire → call → record_usage pattern used by ProviderHandler in the LLM stack.
    """
    provider: BaseEmbeddingProvider
    strategy: QuotaStrategy
    priority: int
    name: str
    _can_count_tokens: bool = True

    def embed(self, text: str) -> List[float]:
        """Acquire quota, call provider embed, and record actual token usage."""
        self.strategy.update_batch_size(1)
        self.strategy.acquire(max(1, len(text) // 4))
        if self._can_count_tokens:
            try:
                token = self.provider.count_tokens(text)
            except Exception as e:
                logger.error("count_tokens_failed", provider=self.name, error=str(e))
                self._can_count_tokens = False
                token = len(text) // 4
        else:
            token = len(text) // 4
        result = self.provider.embed(text)
        if result is not None:
            self.strategy.record_usage(token)
        return result

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Acquire quota for a batch, call provider embed_batch, and record token usage."""
        estimated = max(1, sum(len(t) for t in texts) // 4)
        self.strategy.update_batch_size(len(texts))
        self.strategy.acquire(estimated)
        result = self.provider.embed_batch(texts)
        if result is not None:
            if self._can_count_tokens:
                try:
                    actual = self.provider.count_tokens(" ".join(texts))
                except Exception as e:
                    logger.error("count_tokens_failed", provider=self.name, error=str(e))
                    self._can_count_tokens = False
                    actual = estimated
            else:
                actual = estimated
            self.strategy.record_usage(actual)
        return result


class ResilientEmbeddingService(EmbeddingService):
    """
    Composite EmbeddingService that tries multiple providers in order.
    """

    def __init__(self, handlers: List[EmbeddingProviderHandler]) -> None:
        self._handlers = sorted(handlers, key=lambda h: h.priority)
        self._rate_limit_tracker = RateLimitedProviderTracker()

    @property
    def exhausted_providers(self) -> List[str]:
        """provider names that raised RateLimitExhausted at least once this run."""
        return self._rate_limit_tracker.exhausted

    def embed(self, text: str) -> Optional[List[float]]:
        """Try each embedding handler in priority order, falling back on rate-limit or failure."""

        handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            try:
                result = handler.embed(text)

                if result is not None:
                    return result

                logger.warning(
                    "embedding_provider_returned_none",
                    provider=handler.name,
                )

            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning(
                    "embedding_provider_daily_limit_reached",
                    provider=handler.name,
                )

                self._handlers.remove(handler)
                self._handlers.append(handler)

                logger.warning(
                    "embedding_provider_moved_to_end",
                    provider=handler.name,
                )

            except Exception as e:
                logger.error(
                    "embedding_provider_failed",
                    provider=handler.name,
                    error=str(e),
                )

        logger.error("all_embedding_providers_exhausted")
        return None

    def embed_batch(
        self,
        texts: List[str],
    ) -> Optional[List[List[float]]]:
        """Try each embedding handler in priority order for batch embed, falling back on failure."""

        handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            try:
                result = handler.embed_batch(texts)

                if result is not None:
                    return result

                logger.warning(
                    "embedding_provider_batch_returned_none",
                    provider=handler.name,
                )

            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning(
                    "embedding_provider_daily_limit_reached",
                    provider=handler.name,
                )

                self._handlers.remove(handler)
                self._handlers.append(handler)

                logger.warning(
                    "embedding_provider_moved_to_end",
                    provider=handler.name,
                )

            except Exception as e:
                logger.error(
                    "embedding_provider_failed",
                    provider=handler.name,
                    error=str(e),
                )

        logger.error("all_embedding_providers_exhausted")
        return None


# ---------------------------------------------------------------------------
# 024-async-pipeline-refactor: async siblings, not replacements. See the
# module-level note above ResilientLLMService for why these are new classes
# rather than in-place async conversions (research.md item 3).
# ---------------------------------------------------------------------------

@dataclass
class AsyncProviderHandler:
    """Async sibling of ProviderHandler."""
    provider: Any
    strategy: QuotaStrategy
    priority: int
    name: str

    async def analyze(self, content: str, prompt: str) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        self.strategy.acquire(estimated_tokens=len(content) // 4)
        result = await self.provider.analyze(content, prompt)
        if result is not None:
            _, metadata = result
            self.strategy.record_usage(metadata.input_tokens + metadata.output_tokens)
        return result

    async def translate(self, content: str, prompt: str) -> Optional[str]:
        self.strategy.acquire(estimated_tokens=len(content) // 4)
        result = await self.provider.translate(content, prompt)
        if result is not None:
            self.strategy.record_usage(len(content) // 4 + len(result) // 4)
        return result

    async def generate(self, prompt: str) -> Optional[str]:
        self.strategy.acquire(estimated_tokens=len(prompt) // 4)
        result = await self.provider.generate(prompt)
        if result is not None:
            self.strategy.record_usage(len(prompt) // 4 + len(result) // 4)
        return result


class AsyncResilientLLMService:
    """Async sibling of ResilientLLMService — same priority-ordered-fallback
    shape, async def throughout, now capacity-aware (User Story 4): each
    dispatch call scans for handlers with spare capacity via
    `self._provider_selector.select()` and tries those first, falling back to
    the full priority-ordered list (today's behavior) for anything not
    currently available. See contracts/provider-selector-port.md."""

    def __init__(self, handlers: List[AsyncProviderHandler], provider_selector: Optional[ProviderSelector] = None) -> None:
        self._handlers = sorted(handlers, key=lambda h: h.priority)
        self._rate_limit_tracker = RateLimitedProviderTracker()
        self._provider_selector = provider_selector or PriorityFirstProviderSelector()

    @property
    def exhausted_providers(self) -> List[str]:
        return self._rate_limit_tracker.exhausted

    def _dispatch_order(self, handlers_snapshot: List[AsyncProviderHandler]) -> List[AsyncProviderHandler]:
        """Handlers with current capacity first (selector's preferred order),
        then every remaining handler in its original (priority) order as a
        fallback — preserves "try everyone before giving up" semantics while
        preferring whichever model has headroom right now (FR-010/FR-011).
        No `await` between this call and the caller's first dispatch attempt
        — see contracts/provider-selector-port.md's atomicity requirement."""
        selected = self._provider_selector.select(handlers_snapshot)
        selected_set = set(selected)
        remaining = [i for i in range(len(handlers_snapshot)) if i not in selected_set]
        return [handlers_snapshot[i] for i in selected + remaining]

    async def analyze(self, content: str, prompt: str) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        handlers_snapshot = self._dispatch_order(list(self._handlers))
        for handler in handlers_snapshot:
            try:
                result = await handler.analyze(content, prompt)
                if result is not None:
                    return result
                logger.warning("provider_returned_none", provider=handler.name)
            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning("provider_daily_limit_reached", provider=handler.name)
                # No lock needed: no `await` between remove()/append() below,
                # so this is atomic under asyncio's cooperative scheduling —
                # see research.md item 7. Do not add an await between them.
                self._handlers.remove(handler)
                self._handlers.append(handler)
                logger.warning("provider_moved_to_end", provider=handler.name)
            except Exception as e:
                logger.error("provider_failed", provider=handler.name, error=str(e))
        logger.error("all_providers_exhausted")
        return None

    async def translate(self, content: str, prompt: str) -> Optional[str]:
        handlers_snapshot = self._dispatch_order(list(self._handlers))
        for handler in handlers_snapshot:
            try:
                result = await handler.translate(content, prompt)
                if result is not None:
                    return result
                logger.warning("provider_translate_returned_none", provider=handler.name)
            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning("provider_daily_limit_reached", provider=handler.name)
                self._handlers.remove(handler)
                self._handlers.append(handler)
                logger.warning("provider_moved_to_end", provider=handler.name)
            except Exception as e:
                logger.error("provider_translate_failed", provider=handler.name, error=str(e))
        logger.error("all_providers_exhausted_translate")
        return None

    async def generate(self, prompt: str) -> Optional[str]:
        handlers_snapshot = self._dispatch_order(list(self._handlers))
        for handler in handlers_snapshot:
            try:
                result = await handler.generate(prompt)
                if result is not None:
                    return result
                logger.warning("provider_generate_returned_none", provider=handler.name)
            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning("provider_daily_limit_reached", provider=handler.name)
                self._handlers.remove(handler)
                self._handlers.append(handler)
                logger.warning("provider_moved_to_end", provider=handler.name)
            except Exception as e:
                logger.error("provider_generate_failed", provider=handler.name, error=str(e))
        logger.error("all_providers_exhausted_generate")
        return None


@dataclass
class AsyncEmbeddingProviderHandler:
    """Async sibling of EmbeddingProviderHandler."""
    provider: Any
    strategy: QuotaStrategy
    priority: int
    name: str
    _can_count_tokens: bool = True

    async def embed(self, text: str) -> List[float]:
        self.strategy.update_batch_size(1)
        self.strategy.acquire(max(1, len(text) // 4))
        if self._can_count_tokens:
            try:
                token = await self.provider.count_tokens(text)
            except Exception as e:
                logger.error("count_tokens_failed", provider=self.name, error=str(e))
                self._can_count_tokens = False
                token = len(text) // 4
        else:
            token = len(text) // 4
        result = await self.provider.embed(text)
        if result is not None:
            self.strategy.record_usage(token)
        return result

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        estimated = max(1, sum(len(t) for t in texts) // 4)
        self.strategy.update_batch_size(len(texts))
        self.strategy.acquire(estimated)
        result = await self.provider.embed_batch(texts)
        if result is not None:
            if self._can_count_tokens:
                try:
                    actual = await self.provider.count_tokens(" ".join(texts))
                except Exception as e:
                    logger.error("count_tokens_failed", provider=self.name, error=str(e))
                    self._can_count_tokens = False
                    actual = estimated
            else:
                actual = estimated
            self.strategy.record_usage(actual)
        return result


class AsyncResilientEmbeddingService:
    """Async sibling of ResilientEmbeddingService — capacity-aware dispatch
    (User Story 4), same shape as AsyncResilientLLMService above."""

    def __init__(self, handlers: List[AsyncEmbeddingProviderHandler], provider_selector: Optional[ProviderSelector] = None) -> None:
        self._handlers = sorted(handlers, key=lambda h: h.priority)
        self._rate_limit_tracker = RateLimitedProviderTracker()
        self._provider_selector = provider_selector or PriorityFirstProviderSelector()

    @property
    def exhausted_providers(self) -> List[str]:
        return self._rate_limit_tracker.exhausted

    def _dispatch_order(self, handlers_snapshot: List[AsyncEmbeddingProviderHandler]) -> List[AsyncEmbeddingProviderHandler]:
        """See AsyncResilientLLMService._dispatch_order above."""
        selected = self._provider_selector.select(handlers_snapshot)
        selected_set = set(selected)
        remaining = [i for i in range(len(handlers_snapshot)) if i not in selected_set]
        return [handlers_snapshot[i] for i in selected + remaining]

    async def embed(self, text: str) -> Optional[List[float]]:
        handlers_snapshot = self._dispatch_order(list(self._handlers))
        for handler in handlers_snapshot:
            try:
                result = await handler.embed(text)
                if result is not None:
                    return result
                logger.warning("embedding_provider_returned_none", provider=handler.name)
            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning("embedding_provider_daily_limit_reached", provider=handler.name)
                self._handlers.remove(handler)
                self._handlers.append(handler)
                logger.warning("embedding_provider_moved_to_end", provider=handler.name)
            except Exception as e:
                logger.error("embedding_provider_failed", provider=handler.name, error=str(e))
        logger.error("all_embedding_providers_exhausted")
        return None

    async def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        handlers_snapshot = self._dispatch_order(list(self._handlers))
        for handler in handlers_snapshot:
            try:
                result = await handler.embed_batch(texts)
                if result is not None:
                    return result
                logger.warning("embedding_provider_batch_returned_none", provider=handler.name)
            except RateLimitExhausted:
                self._rate_limit_tracker.mark_exhausted(handler.name)
                logger.warning("embedding_provider_daily_limit_reached", provider=handler.name)
                self._handlers.remove(handler)
                self._handlers.append(handler)
                logger.warning("embedding_provider_moved_to_end", provider=handler.name)
            except Exception as e:
                logger.error("embedding_provider_failed", provider=handler.name, error=str(e))
        logger.error("all_embedding_providers_exhausted")
        return None