from typing import Any, Callable, Dict, Optional

import jmespath

from src.modules.collection.domain.services import MetricExtractor


class JsonPathMetricExtractor(MetricExtractor):
    """Generic extractor for extractor_type='json_path' metric_definitions rows.

    fetch() delegates to a provider-keyed fetcher callable (an HTTP call — this
    is code, registered once per provider in resilient_metrics_service.py).
    extract() evaluates a JMESPath expression against the raw response — this
    part is pure declarative configuration, safe to store in the DB verbatim.
    """

    def __init__(self, provider_name: str, fetcher: Callable[[Dict[str, str]], Optional[dict]]) -> None:
        self._provider_name = provider_name
        self._fetcher = fetcher

    def fetch(self, article_identifiers: Dict[str, str]) -> Optional[dict]:
        return self._fetcher(article_identifiers)

    def extract(self, raw_response: dict, extractor_spec: Dict[str, Any]) -> Optional[Any]:
        path = extractor_spec.get("path")
        if not path:
            return None
        return jmespath.search(path, raw_response)
