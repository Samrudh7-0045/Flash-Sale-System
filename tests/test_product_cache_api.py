
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event

import app.main as main_module
from app.database import SessionLocal, engine
from app.models import Order, Product


def test_products_endpoint_uses_cache(monkeypatch):
    store = {}
    db = SessionLocal()
    product = Product(
        name=f"Cache API Test {uuid4().hex[:8]}",
        price=Decimal("12.50"),
        stock=7,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    product_id = product.id
    db.close()

    query_count = 0

    def count_selects(
        conn, cursor, statement, parameters, context, executemany
    ):
        nonlocal query_count
        if statement.lstrip().upper().startswith("SELECT"):
            query_count += 1

    def fake_get():
        return store.get("products")

    def fake_cache(products):
        store["products"] = products

    monkeypatch.setattr(main_module, "get_cached_products", fake_get)
    monkeypatch.setattr(main_module, "cache_products", fake_cache)

    event.listen(engine, "before_cursor_execute", count_selects)

    try:
        with TestClient(main_module.app) as client:
            before_first_request = query_count
            first = client.get("/products")
            first_request_queries = query_count - before_first_request

            before_second_request = query_count
            second = client.get("/products")
            second_request_queries = query_count - before_second_request

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()
        assert any(p["id"] == product_id for p in second.json())
        assert "products" in store

        # First request reads products from PostgreSQL.
        assert first_request_queries >= 1

        # Second request serves the cached list without a product SELECT.
        assert second_request_queries == 0

    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

        cleanup_db = SessionLocal()
        try:
            cleanup_db.query(Product).filter(
                Product.id == product_id
            ).delete(synchronize_session=False)
            cleanup_db.commit()
        finally:
            cleanup_db.close()


def test_successful_order_invalidates_product_cache(monkeypatch):
    db = SessionLocal()
    product = Product(
        name=f"Cache Invalidation Test {uuid4().hex[:8]}",
        price=Decimal("10.00"),
        stock=5,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    product_id = product.id
    db.close()

    invalidated = []

    monkeypatch.setattr(
        main_module,
        "claim_reservation",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        main_module,
        "release_stock",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        main_module,
        "invalidate_products_cache",
        lambda: invalidated.append(True),
    )

    idempotency_key = f"cache-invalidation-{uuid4()}"

    try:
        with TestClient(main_module.app) as client:
            response = client.post(
                "/orders",
                json={
                    "product_id": product_id,
                    "quantity": 1,
                    "reservation_token": "fake-test-token",
                    "idempotency_key": idempotency_key,
                },
            )

        assert response.status_code == 201
        assert invalidated == [True]

        verify_db = SessionLocal()
        try:
            saved_product = verify_db.get(Product, product_id)
            assert saved_product.stock == 4
        finally:
            verify_db.close()

    finally:
        cleanup_db = SessionLocal()
        try:
            cleanup_db.query(Order).filter(
                Order.idempotency_key == idempotency_key
            ).delete(synchronize_session=False)
            cleanup_db.query(Product).filter(
                Product.id == product_id
            ).delete(synchronize_session=False)
            cleanup_db.commit()
        finally:
            cleanup_db.close()
