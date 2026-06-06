# Contract: LLMService Interface

**Feature**: 003-llm-analysis | **Date**: 2026-05-29

The `LLMService` abstract base class defines the contract that all LLM provider implementations must satisfy. It lives in the domain layer (`src/modules/intelligence/domain/services/llm_service.py`) and is the only point of coupling between the application layer and LLM infrastructure.

---

## Interface

### `analyze(content: str, prompt: str) → Optional[Tuple[AnalysisContent, AnalysisMetadata]]`

Analyzes article content using the LLM and returns structured results.

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | str | Full article text (pre-truncated by caller for ArXiv sources) |
| `prompt` | str | Rendered, topic-specific analysis instruction |

**Returns**:
- `(AnalysisContent, AnalysisMetadata)` on success
- `None` on any failure (rate limit, parse error, API error after retries)

**Caller contract**:
- The caller (AnalyzeArticleUseCase) is responsible for rendering the correct prompt variant based on topic mode before calling this method.
- The caller treats `None` as a fatal analysis failure and records `AnalysisResult(success=False)`.

**Implementer contract**:
- MUST NOT raise exceptions to the caller (except `RateLimitExhausted`, which ResilientLLMService handles internally).
- MUST return `None` rather than raising on parse errors, validation failures, or exhausted retries.
- MUST populate `AnalysisMetadata.model_used`, `input_tokens`, and `output_tokens`.

---

### `translate(content: str, prompt: str) → Optional[str]`

Translates a text string into a target language.

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | str | Text to translate |
| `prompt` | str | Translation instruction specifying target language |

**Returns**:
- Translated string on success
- `None` on failure

**Note**: Translation is used by the 004-translation pipeline, not by this feature. It is included here because it is part of the `LLMService` domain interface.

---

## Implementations

| Class | Location | Description |
|-------|----------|-------------|
| `ResilientLLMService` | `src/infrastructure/intelligence/llm/resilient_llm_service.py` | Composite: ordered fallback chain over multiple providers |
| `ClaudeProvider` | `src/infrastructure/intelligence/llm/providers/claude_provider.py` | Anthropic Claude API |
| `GeminiProvider` | `src/infrastructure/intelligence/llm/providers/gemini_provider.py` | Google Gemini API |
| `OpenRouterProvider` | `src/infrastructure/intelligence/llm/providers/openrouter_provider.py` | OpenRouter HTTP API |

---

## Error Taxonomy

| Error | Raised By | Handled By |
|-------|-----------|------------|
| `RateLimitExhausted` | `SlidingWindowStrategy.acquire()` or provider on daily quota | `ResilientLLMService` — demotes provider, tries next |
| JSON parse / validation failure | `BaseProvider._validate_response()` | `BaseProvider` — returns `None`, logs warning |
| Transient API error | Provider API call | `BaseProvider` with `@retry` (3× exp. backoff) |
| All providers exhausted | `ResilientLLMService.analyze()` | Returns `None` to `AnalyzeArticleUseCase` |
| `None` from `LLMService.analyze()` | `AnalyzeArticleUseCase.execute()` | Returns `AnalysisResult(success=False, exception_type="LLMAnalysisError")` |

---

## Required JSON Output Schema (from LLM)

All providers must produce a response parseable into the following JSON structure:

```json
{
  "tag_groups": [
    {
      "group": "snake_case_key",
      "tags": ["tag1", "tag2"]
    }
  ],
  "summary": "2-3 sentence overview",
  "pain_points": "Problems identified",
  "insights": "Key learnings",
  "innovations": "Novel contributions"
}
```

**Validation rules**:
- All five top-level keys (`tag_groups`, `summary`, `pain_points`, `insights`, `innovations`) must be present.
- Missing any required key → provider returns `None` (logged as warning).
- String fields may be empty strings but not absent.
- `tag_groups` may be an empty array.
