from typing import Any, Dict, List


def load_active_providers(session) -> List[Dict[str, Any]]:
    """Load active LLM provider configs from DB, sorted by priority.

    Returns dicts in the same shape bootstrap.py expects:
      {'name', 'model', 'api_key_env', 'priority', 'strategy'}
    where strategy is {'type': 'sliding_window', 'rpm', 'tpm', 'rpd'}
    or {'type': 'noop'} when any rate-limit field is None.
    """
    from models.llm_provider import LlmProvider

    providers = (
        session.query(LlmProvider)
        .filter(LlmProvider.is_active.is_(True))
        .order_by(LlmProvider.priority)
        .all()
    )

    result = []
    for p in providers:
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
