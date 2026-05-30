# Contract: AnalysesTranslationRepository + TagTranslationRepository

**Feature**: 004-translation | **Date**: 2026-05-29

## AnalysesTranslationRepository (Domain Interface)

```python
class AnalysesTranslationRepository(ABC):
    @abstractmethod
    def save(self, content: AnalysesContent) -> AnalysesContent:
        """Upsert: update if (analysis_id, language) exists, insert otherwise."""

    @abstractmethod
    def find_by_analysis_id_and_language(self, analysis_id: UUID, language: str) -> Optional[AnalysesContent]:
        """Return the translation for a specific analysis and language, or None."""

    @abstractmethod
    def exists(self, analysis_id: UUID, language: str) -> bool:
        """Return True if a translation exists for (analysis_id, language)."""

    @abstractmethod
    def find_analyses_without_translation(self, language: str, limit: int) -> list:
        """Return analyses that have no translation row for the given language,
        up to `limit` results."""
```

### Behavioral Guarantees

- `save()` is idempotent — calling it twice with the same `(analysis_id, language)` does not create duplicates.
- `exists()` is a lightweight check (COUNT query) — does not fetch content.
- `find_analyses_without_translation()` excludes analyses that already have a translation in the target language.

---

## TagTranslationRepository (Domain Interface)

```python
class TagTranslationRepository(ABC):
    @abstractmethod
    def save_tag_translation(self, tag_id: UUID, language: str, name: str) -> None:
        """Upsert: update if (tag_id, language) exists, insert otherwise."""

    @abstractmethod
    def find_tags_without_translation(self, language: str, limit: int) -> list:
        """Return tags that have no translation row for the given language,
        up to `limit` results. Each element includes tag_id and name."""

    @abstractmethod
    def save_group_translation(self, group_id: UUID, language: str, display_name: str, description: Optional[str]) -> None:
        """Upsert: update if (group_id, language) exists, insert otherwise."""

    @abstractmethod
    def find_groups_without_translation(self, language: str, limit: int) -> list:
        """Return tag groups that have no translation row for the given language,
        up to `limit` results. Each element includes group_id, display_name, and description."""
```

### Behavioral Guarantees

- Both `save_*` methods are idempotent upserts.
- `find_tags_without_translation()` uses `~Tag.translations.any(language == target)` filter.
- `find_groups_without_translation()` uses `~TagGroupDefinition.translations.any(language == target)` filter.
