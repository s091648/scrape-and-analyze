"""Module-level CacheGateway singleton, mirroring database.py's engine/SessionLocal pattern."""
from shared.cache import CacheGateway, RedisCacheGateway
from backend.config import CACHE_REDIS_URL

cache_gateway: CacheGateway = RedisCacheGateway(redis_url=CACHE_REDIS_URL)


def get_cache_gateway() -> CacheGateway:
    return cache_gateway
