import json

from app.redis_client import redis_client

PRODUCTS_CACHE_KEY = "products:all"
CACHE_TTL_SECONDS = 30


def get_cached_products():
    try:
        cached = redis_client.get(PRODUCTS_CACHE_KEY)
        if cached is None:
            return None
        return json.loads(cached)
    except Exception as exc:
        print("PRODUCT CACHE READ ERROR:", repr(exc))
        return None


def cache_products(products: list[dict]) -> None:
    try:
        redis_client.set(
            PRODUCTS_CACHE_KEY,
            json.dumps(products),
            ex=CACHE_TTL_SECONDS,
        )
    except Exception as exc:
        print("PRODUCT CACHE WRITE ERROR:", repr(exc))


def invalidate_products_cache() -> None:
    try:
        redis_client.delete(PRODUCTS_CACHE_KEY)
    except Exception as exc:
        print("PRODUCT CACHE INVALIDATION ERROR:", repr(exc))