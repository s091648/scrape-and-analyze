# Feature Specification: Translation

**Feature Branch**: `004-translation`

**Created**: 2026-05-29

**Status**: Draft

**Input**: Brownfield spec — describes existing behavior of the translation capability as it currently stands.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auto-translation after analysis (Priority: P1)

After an article is analyzed and its tags are normalized, the system automatically translates the analysis content (summary, pain points, insights, innovations) and the article's tags and tag groups into each configured target language. This happens without any manual intervention as part of the scrape-analyze pipeline.

**Why this priority**: Auto-translation is the primary value delivery — it ensures non-English readers can access insights immediately after analysis completes.

**Independent Test**: Run the full pipeline on a new article. After analysis succeeds, verify that translation rows exist in all configured target languages for the analysis content, tags, and tag groups.

**Acceptance Scenarios**:

1. **Given** an article has been analyzed and tags normalized, **When** the tag normalization event is published, **Then** the system translates the analysis content into every language listed in the translation-languages configuration, one language at a time.
2. **Given** an article has been analyzed but no English translation row exists, **When** the auto-translation handler runs, **Then** the handler logs a warning and skips translation (English content is a prerequisite).
3. **Given** auto-translation fails for a specific language, **When** the LLM returns no result or throws an exception, **Then** a translation-failed event is published with the analysis ID, article ID, and error details, and the failed task is persisted for later retry.

---

### User Story 2 - Manual batch translation via CLI (Priority: P2)

An operator can run a CLI command to translate a batch of untranslated analyses, tags, and tag groups into a specified language. This is useful for backfilling translations when a new language is added, or retrying previously failed translations.

**Why this priority**: Manual translation is the operational escape hatch — it handles new language rollouts and failure recovery that the auto-flow doesn't cover.

**Independent Test**: Run the CLI translation command with a specific language and limit. Verify that the specified number of analyses, tags, and tag groups are translated and persisted.

**Acceptance Scenarios**:

1. **Given** there are 20 analyses without zh-TW translation, **When** the operator runs the translate command with language=zh-TW and limit=10, **Then** exactly 10 analyses are translated, along with up to 10 tags and 10 tag groups that lack zh-TW translations.
2. **Given** an operator specifies an unsupported language code, **When** the translate command runs, **Then** the command exits with an error message listing the supported languages.
3. **Given** all analyses already have translations in the target language, **When** the translate command runs, **Then** no LLM calls are made and the command reports zero translations performed.

---

### User Story 3 - Translation deduplication (Priority: P3)

When a translation already exists for a given analysis (or tag, or tag group) in a target language, the system does not re-translate. It returns the existing translation instead. This prevents wasted LLM calls and ensures idempotency.

**Why this priority**: Deduplication is essential for correctness and cost-efficiency, but it is a supporting behavior rather than the primary user-facing feature.

**Independent Test**: Call translation twice for the same analysis and language. On the second call, verify that no LLM call is made and the existing translation is returned.

**Acceptance Scenarios**:

1. **Given** an analysis already has a zh-TW translation row, **When** article translation is requested for zh-TW on that analysis, **Then** the existing translation is returned without calling the LLM.
2. **Given** a tag already has a zh-TW translation, **When** batch tag translation runs for zh-TW, **Then** that tag is excluded from the query results and not sent to the LLM.
3. **Given** a tag group already has a ja translation, **When** batch group translation runs for ja, **Then** that group is excluded from the query and not re-translated.

---

### Edge Cases

- What happens when the LLM returns a malformed response missing expected section headers (Summary, Pain Points, etc.)? The parser uses regex to split by section headers; unmatched sections remain as empty strings in the parsed result.
- What happens when the LLM returns fewer lines than the number of tags sent? Unmatched tags are counted as "failed" in the result summary.
- What happens when the LLM returns fewer lines than the number of tag groups sent? Unmatched groups are counted as "failed" in the result summary.
- What happens when all LLM providers are exhausted (rate-limited or errored)? The translation returns a failure result with all content fields empty.
- What happens when a translation save fails after a successful LLM call? The use case returns success=False; the translated content is lost and must be retried.
- What happens when empty source fields (e.g., no pain points) are passed to the translation prompt? They are substituted with the literal string "(empty)" in the prompt.
- What happens when a tag group has no description? The group is formatted as "display_name |" (pipe with empty second part), and the parser treats it as display_name only.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically translate article analysis content (summary, pain points, insights, innovations) into every configured target language after tag normalization completes.
- **FR-002**: System MUST automatically translate tag names and tag group display names/descriptions into every configured target language after article translation completes for that language.
- **FR-003**: System MUST allow manual batch translation of analyses, tags, and tag groups via a CLI command with configurable language and limit.
- **FR-004**: System MUST skip translation for any analysis, tag, or tag group that already has a translation in the target language (deduplication).
- **FR-005**: System MUST persist translation failures as failed tasks with the analysis ID, article ID, task type, error details, and context, so they can be retried later.
- **FR-006**: System MUST validate the target language code against supported languages before starting translation, rejecting unsupported codes with a clear error.
- **FR-007**: System MUST use English analysis content as the source for all translations; if no English translation row exists, auto-translation MUST be skipped with a warning.
- **FR-008**: System MUST substitute empty source fields (summary, pain points, insights, innovations) with "(empty)" in the translation prompt.
- **FR-009**: System MUST parse the LLM translation response into structured sections (summary, pain points, insights, innovations) using section header markers.
- **FR-010**: System MUST parse the LLM tag translation response line-by-line, matching each line positionally to the corresponding tag ID.
- **FR-011**: System MUST parse the LLM tag group translation response line-by-line, splitting each line on a pipe delimiter into display name and optional description.
- **FR-012**: System MUST count unmatched tags or groups (where the LLM returns fewer lines than requested) as failures and report them in the batch result summary.
- **FR-013**: System MUST fall back to the next available LLM provider when the current provider fails or is rate-limited, deprioritizing exhausted providers.
- **FR-014**: System MUST return a failure result (all content fields empty, success=False) when all LLM providers are exhausted.
- **FR-015**: System MUST support configuring target languages via a comma-separated environment variable, defaulting to zh-TW.
- **FR-016**: System MUST use upsert semantics when persisting translations — if a row already exists for the same parent and language, it is updated in place rather than duplicated.
- **FR-017**: System MUST tag translation failures with a distinct task type ("translate_article") so they can be filtered and retried independently of other failure categories.

### Key Entities

- **Analysis Translation**: A translated version of an article's analysis content in a specific language. Identified by the pair (analysis_id, language). Contains translated summary, pain points, insights, and innovations. Each analysis can have multiple translations in different languages.
- **Tag Translation**: A translated tag name in a specific language. Identified by the pair (tag_id, language). Contains the translated name. Each tag can have multiple translations in different languages.
- **Tag Group Translation**: A translated tag group display name and description in a specific language. Identified by the pair (tag_group_definition_id, language). Contains translated display_name and optional description. Each tag group can have multiple translations in different languages.
- **Translation Prompt**: A template with language-specific placeholders that produces the instruction sent to the LLM. Three variants exist: article analysis prompt, tag name prompt, and tag group prompt. Contains a mapping of language codes to human-readable language names for prompt rendering.
- **Translation Result**: The outcome of a translation attempt, carrying the translated content (or empty content on failure), the target language, the analysis ID, and a success flag.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every article that completes the full pipeline (scrape → analyze → tag normalization) automatically has translations in all configured languages within the same pipeline run.
- **SC-002**: Manual translation backfill processes exactly the requested number of items per batch without re-translating already-translated content.
- **SC-003**: Translation failures are captured as retryable failed tasks with sufficient context (analysis ID, article ID, error details) for automated or manual retry.
- **SC-004**: LLM provider fallback ensures translation succeeds whenever at least one provider is available, without requiring manual intervention.
- **SC-005**: Duplicate translation calls for the same analysis and language produce no additional LLM cost (deduplication is effective).

## Assumptions

- English content (language code "en") always exists as the source translation before other languages are translated. The system does not support translating from non-English sources.
- The set of supported language codes is fixed: zh-TW, zh-CN, ja, ko, es, fr, de. Adding a new language requires updating the language name mapping in the prompt value objects.
- Frontend i18n (client-side UI string translation) is a separate concern from server-side content translation and is not part of this capability.
- Tag and group translation during auto-triggered flow uses a fixed batch limit of 50; this is not configurable per event.
- The CLI uses the same limit for article, tag, and group translation — there are no separate limits per entity type.
- Translation prompt templates are defined as domain value objects and are not user-configurable at runtime.
