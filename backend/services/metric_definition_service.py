from uuid import UUID

from sqlalchemy.orm import Session

from backend.schemas.metric_definition import MetricDefinitionDisplayOut


def get_enabled_metric_display(db: Session) -> list[MetricDefinitionDisplayOut]:
    """Enabled catalog metrics for public display consumption (article badges, sort
    options) — one row per metric_key, no provider/extraction internals."""
    from models.metric_definition import MetricDefinition

    rows = (
        db.query(MetricDefinition)
        .filter(MetricDefinition.enabled.is_(True))
        .order_by(MetricDefinition.metric_key)
        .all()
    )
    return [
        MetricDefinitionDisplayOut(
            metric_key=row.metric_key,
            label_i18n_key=row.label_i18n_key,
            icon_name=row.icon_name,
            format_hint=row.format_hint,
            unit=row.unit,
        )
        for row in rows
    ]


def get_all_metric_definitions(db: Session):
    """Every metric_key row (including disabled) for the admin page — one row per
    metric_key, not per provider."""
    from models.metric_definition import MetricDefinition
    return db.query(MetricDefinition).order_by(MetricDefinition.metric_key).all()


def update_metric_definition(db: Session, definition_id: UUID, *, enabled: bool | None, icon_name: str | None):
    """Updates `enabled` and/or `icon_name` only (icon_name already whitelist-validated by
    the schema layer) — extraction/label configuration is never touched here (FR-041)."""
    from models.metric_definition import MetricDefinition
    obj = db.query(MetricDefinition).filter(MetricDefinition.id == definition_id).first()
    if not obj:
        return None
    if enabled is not None:
        obj.enabled = enabled
    if icon_name is not None:
        obj.icon_name = icon_name
    db.commit()
    db.refresh(obj)
    return obj
