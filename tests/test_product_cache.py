import json

from app.product_cache import (
    CACHE_TTL_SECONDS,
    PRODUCTS_CACHE_KEY,
    cache_products,
    get_cached_products,
    invalidate_products_cache,
)


def test_product_cache_round_trip_and_invalidation(monkeypatch):
    store = {}

    def fake_get(key):
        return store.get(key)

    def fake_set(key, value, ex):
        assert ex == CACHE_TTL_SECONDS
        store[key] = value

    def fake_delete(key):
        store.pop(key, None)

    from app.product_cache import redis_client

    monkeypatch.setattr(redis_client, "get", fake_get)
    monkeypatch.setattr(redis_client, "set", fake_set)
    monkeypatch.setattr(redis_client, "delete", fake_delete)

    products = [{"id": 101, "name": "Test Product", "price": "10.00", "stock": 5}]

    assert get_cached_products() is None

    cache_products(products)
    assert store[PRODUCTS_CACHE_KEY] == json.dumps(products)
    assert get_cached_products() == products

    invalidate_products_cache()
    assert get_cached_products() is None