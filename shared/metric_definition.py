from typing import Any, Dict, List


def load_enabled_metric_definitions(session) -> List[Dict[str, Any]]:
    """Load enabled metrics' provider/extraction config from DB, ordered by
    (metric_key, priority). `metric_definitions` (enabled/display config) and
    `metric_providers` (extraction config) are separate tables as of 2026-07-12 — see
    alembic 23 revision notes — but this function's output shape is unchanged so
    resilient_metrics_service.py needs no changes."""
    from models.metric_definition import MetricDefinition
    from models.metric_provider import MetricProvider

    rows = (
        session.query(MetricDefinition, MetricProvider)
        .join(MetricProvider, MetricProvider.metric_definition_id == MetricDefinition.id)
        .filter(MetricDefinition.enabled.is_(True))
        .order_by(MetricDefinition.metric_key, MetricProvider.priority)
        .all()
    )
    return [
        {
            'metric_key': d.metric_key,
            'provider_name': p.provider_name,
            'priority': p.priority,
            'extractor_type': p.extractor_type,
            'extractor_spec': p.extractor_spec,
        }
        for d, p in rows
    ]
