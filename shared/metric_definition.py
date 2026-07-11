from typing import Any, Dict, List


def load_enabled_metric_definitions(session) -> List[Dict[str, Any]]:
    """Load enabled metric definitions from DB, ordered by (metric_key, priority)."""
    from models.metric_definition import MetricDefinition

    rows = (
        session.query(MetricDefinition)
        .filter(MetricDefinition.enabled.is_(True))
        .order_by(MetricDefinition.metric_key, MetricDefinition.priority)
        .all()
    )
    return [
        {
            'metric_key': d.metric_key,
            'provider_name': d.provider_name,
            'priority': d.priority,
            'extractor_type': d.extractor_type,
            'extractor_spec': d.extractor_spec,
        }
        for d in rows
    ]
