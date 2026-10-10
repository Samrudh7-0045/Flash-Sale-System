from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main_module
from app.database import SessionLocal
from app.models import Order, Product
from app.reservations import release_stock as redis_release_stock


def test_order_succeeds_if_redis_cleanup_fails(monkeypatch):
    db = SessionLocal()
    product = Product(
        name=f"Failure Test {uuid4().hex[:8]}",
        price=Decimal("1.00"),
        stock=5,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    product_id = product.id
    db.close()

    token = None
    idempotency_key = f"failure-test-{uuid4()}"

    try:
        with TestClient(main_module.app) as client:
            reservation = client.post(
                "/reservations",
                json={"product_id": product_id, "quantity": 1},
            )
            assert reservation.status_code == 201
            token = reservation.json()["reservation_token"]

            # Simulate Redis cleanup failing after the DB commit.
            def fail_release(*args, **kwargs):
                raise RuntimeError("Simulated Redis cleanup failure")

            monkeypatch.setattr(
                main_module,
                "release_stock",
                fail_release,
            )

            response = client.post(
                "/orders",
                json={
                    "product_id": product_id,
                    "quantity": 1,
                    "reservation_token": token,
                    "idempotency_key": idempotency_key,
                },
            )

            assert response.status_code == 201

        verify_db = SessionLocal()
        try:
            saved_product = verify_db.get(Product, product_id)
            saved_order = (
                verify_db.query(Order)
                .filter(Order.idempotency_key == idempotency_key)
                .first()
            )

            assert saved_product is not None
            assert saved_product.stock == 4
            assert saved_order is not None
            assert saved_order.product_id == product_id
        finally:
            verify_db.close()

    finally:
        # Use the real cleanup function, not the simulated failure.
        if token is not None:
            try:
                redis_release_stock(product_id, token)
            except Exception as exc:
                print("Test Redis cleanup failed:", repr(exc))

        cleanup_db = SessionLocal()
        try:
            cleanup_db.query(Order).filter(
                Order.product_id == product_id
            ).delete(synchronize_session=False)

            cleanup_db.query(Product).filter(
                Product.id == product_id
            ).delete(synchronize_session=False)

            cleanup_db.commit()
        finally:
            cleanup_db.close()