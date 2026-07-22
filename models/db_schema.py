from enum import Enum


class DbSchema(str, Enum):
    """PostgreSQL schemas mirroring the DDD bounded contexts in src/modules/.

    `auth` and `vectors` are not members here — those schemas predate this
    enum and are managed by their own migrations (01, 21).
    """

    CORE = "core"
    COLLECTION = "collection"
    INTELLIGENCE = "intelligence"
    AI_INFRA = "ai_infra"
    USER_PREFS = "user_prefs"
