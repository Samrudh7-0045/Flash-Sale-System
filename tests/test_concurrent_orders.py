
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import Product, Order
from app.reservations import release_stock

REQUESTS = 10
QUANTITY = 1
IDEMPOTENCY_KEY = f"concurrency-test-{uuid4()}"


def main():
    db = SessionLocal()
    product_id = None

    try:
        # Create isolated test inventory.
        product = Product(
            name=f"Temporary Test Product {uuid4().hex[:8]}",
            price=Decimal("1.00"),
            stock=20,
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id
        db.close()

        barrier = Barrier(REQUESTS)

        def attempt_order(_):
            barrier.wait()

            with TestClient(app, raise_server_exceptions=False) as client:
                reservation = client.post(
                    "/reservations",
                    json={
                        "product_id": product_id,
                        "quantity": QUANTITY,
                    },
                )

                if reservation.status_code != 201:
                    return reservation.status_code, None, None

                token = reservation.json()["reservation_token"]

                response = client.post(
                    "/orders",
                    json={
                        "product_id": product_id,
                        "quantity": QUANTITY,
                        "reservation_token": token,
                        "idempotency_key": IDEMPOTENCY_KEY,
                    },
                )

                return response.status_code, token, response.text

        with ThreadPoolExecutor(max_workers=REQUESTS) as executor:
            results = list(executor.map(attempt_order, range(REQUESTS)))

        print("HTTP status counts:")
        for status in sorted({result[0] for result in results}):
            print(f"  {status}: {sum(r[0] == status for r in results)}")

        db = SessionLocal()
        try:
            final_product = db.get(Product, product_id)
            orders = (
                db.query(Order)
                .filter(Order.product_id == product_id)
                .all()
            )

            print("Initial stock: 20")
            print("Final stock:", final_product.stock)
            print("Orders created:", len(orders))
            print("Stock deducted:", 20 - final_product.stock)
            print(
                "Exactly one order:",
                len(orders) == 1,
            )
            print(
                "Stock deducted once:",
                final_product.stock == 19,
            )
        finally:
            db.close()

        print("\nNon-201 response details:")
        for status, _, body in results:
            if status != 201:
                print(f"  HTTP {status}: {body}")

    finally:
        # Remove test reservations and temporary database records.
        for _, token, _ in locals().get("results", []):
            if token and product_id is not None:
                release_stock(product_id, token)

        if product_id is not None:
            cleanup_db = SessionLocal()
            try:
                cleanup_db.query(Order).filter(
                    Order.product_id == product_id
                ).delete(synchronize_session=False)

                cleanup_db.query(Product).filter(
                    Product.id == product_id
                ).delete(synchronize_session=False)

                cleanup_db.commit()
                print("\nTemporary test data cleaned up.")
            except Exception:
                print("ORDER ERROR:", repr(__import__("sys").exc_info()[1]))
                cleanup_db.rollback()
                raise
            finally:
                cleanup_db.close()
        elif db is not None:
            db.close()


if __name__ == "__main__":
    main()
