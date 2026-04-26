from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

from src.modules.collection.domain.value_objects.selector_config import (
    ArxivConfig,
    BlogConfig,
    RssConfig,
    SelectorConfig,
    _adapter,
)


class SelectorConfigColumn(TypeDecorator):
    """Maps JSONB ↔ typed SelectorConfig Pydantic models.

    Write path: serializes to JSON dict including the 'type' discriminator.
    Read path: deserializes when 'type' field is present (new data).
               Returns raw dict for legacy rows without 'type'; _to_entity()
               handles those via build_selector_config(source_type, raw).
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (RssConfig, BlogConfig, ArxivConfig)):
            return value.model_dump()
        return value

    def process_result_value(self, value, dialect):
        if not value:
            return None
        if "type" in value:
            return _adapter.validate_python(value)
        return value  # legacy: repo handles via build_selector_config()
