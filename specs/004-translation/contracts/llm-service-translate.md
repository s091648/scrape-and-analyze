# Contract: LLMService.translate()

**Feature**: 004-translation | **Date**: 2026-05-29

## Interface

```python
class LLMService(ABC):
    @abstractmethod
    def translate(self, content: str, prompt: str) -> Optional[str]:
        """Translate content according to the given prompt.

        Args:
            content: Source content to translate (always "" for translation use cases)
            prompt: Full translation instruction + source text

        Returns:
            Translated text as a string, or None if all providers fail.
        """
```

## Usage Pattern in Translation

Both `TranslateArticleUseCase` and `TranslateTagsUseCase` call:
```python
self._llm_service.translate("", rendered_prompt)
```

The `content` parameter is always empty string. The full instruction + source text is assembled into the `prompt` parameter by the prompt value objects.

## ResilientLLMService Behavior

1. Iterates through `ProviderHandler` objects sorted by priority.
2. Each handler acquires rate-limit quota, calls `provider.translate(content, prompt)`, records usage.
3. On `RateLimitExhausted`: the provider is deprioritized (moved to end of handler list), iteration continues.
4. On other exceptions: logs error and continues to next provider.
5. If all providers fail: logs `"all_providers_exhausted_translate"` and returns `None`.

## Return Contract

| Condition | Return Value |
|-----------|-------------|
| At least one provider succeeds | `str` (LLM response text) |
| All providers exhausted / failed | `None` |
