from typing import Any, Dict, List


def _build_provider_dicts(orm_rows) -> List[Dict[str, Any]]:
    result = []
    for p in orm_rows:
        if all(v is not None for v in (p.rpm, p.tpm, p.rpd)):
            strategy: Dict[str, Any] = {
                'type': 'sliding_window',
                'rpm': p.rpm,
                'tpm': p.tpm,
                'rpd': p.rpd,
            }
        else:
            strategy = {'type': 'noop'}

        result.append({
            'name': p.name,
            'model': p.model,
            'api_key_env': p.api_key_env,
            'priority': p.priority,
            'strategy': strategy,
        })
    return result


def load_active_providers(session) -> List[Dict[str, Any]]:
    """Load active LLM provider configs from DB, sorted by priority."""
    from models.llm_provider import LlmProvider

    rows = (
        session.query(LlmProvider)
        .filter(LlmProvider.is_active.is_(True), LlmProvider.type == 'llm')
        .order_by(LlmProvider.priority)
        .all()
    )
    return _build_provider_dicts(rows)


def load_active_embedding_providers(session) -> List[Dict[str, Any]]:
    """Load active embedding provider configs from DB, sorted by priority."""
    from models.llm_provider import LlmProvider

    rows = (
        session.query(LlmProvider)
        .filter(LlmProvider.is_active.is_(True), LlmProvider.type == 'embedding')
        .order_by(LlmProvider.priority)
        .all()
    )
    return _build_provider_dicts(rows)


def load_active_multimodal_provider(session) -> Dict[str, Any] | None:
    """Load the highest-priority active multimodal provider config from DB."""
    from models.llm_provider import LlmProvider

    row = (
        session.query(LlmProvider)
        .filter(LlmProvider.is_active.is_(True), LlmProvider.type == 'multimodal')
        .order_by(LlmProvider.priority)
        .first()
    )
    if not row:
        return None
    return _build_provider_dicts([row])[0]
