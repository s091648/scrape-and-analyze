from dataclasses import dataclass


@dataclass(frozen=True)
class SourceEntry:
    value: str
    label: str


SOURCE_CATEGORIES: dict[str, list[SourceEntry]] = {
    "aggregator": [
        SourceEntry("openalex", "OpenAlex"),
        SourceEntry("semantic_scholar", "Semantic Scholar"),
    ],
    "scraper": [
        SourceEntry("arxiv", "arXiv"),
        SourceEntry("rss", "RSS"),
        SourceEntry("blog", "Blog"),
    ],
}

AGGREGATOR_SOURCES: frozenset[str] = frozenset(
    e.value for e in SOURCE_CATEGORIES["aggregator"]
)
