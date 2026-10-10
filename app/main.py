from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, Product
from app.reservations import (
    claim_reservation,
    release_stock,
    reserve_stock,
    unclaim_reservation,
)
from app.schemas import (
    OrderCreate,
    OrderResponse,
    ProductResponse,
    ReservationCreate,
    ReservationResponse,
)
from app.product_cache import (
    cache_products,
    get_cached_products,
    invalidate_products_cache,
)
app = FastAPI(title="Flash-Sale Inventory System")


def safe_release(product_id: int, token: str) -> None:
    """Attempt Redis cleanup without hiding the original result."""
    try:
        release_stock(product_id, token)
    except Exception as exc:
        print("RESERVATION RELEASE ERROR:", repr(exc))


def safe_unclaim(product_id: int, token: str) -> None:
    """Restore a claim only when the database commit did not succeed."""
    try:
        unclaim_reservation(product_id, token)
    except Exception as exc:
        print("RESERVATION UNCLAIM ERROR:", repr(exc))


@app.get("/")
def root():
    return {"message": "Flash-Sale Inventory System is running"}


@app.get("/products", response_model=list[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    cached_products = get_cached_products()

    if cached_products is not None:
        return cached_products

    products = db.query(Product).all()

    result = [
        {
            "id": product.id,
            "name": product.name,
            "price": str(product.price),
            "stock": product.stock,
        }
        for product in products
    ]

    cache_products(result)
    return result

@app.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=201,
)
def create_reservation(data: ReservationCreate):
    token = reserve_stock(data.product_id, data.quantity)

    if token is None:
        raise HTTPException(
            status_code=409,
            detail="Product unavailable or insufficient stock",
        )

    return ReservationResponse(
        product_id=data.product_id,
        quantity=data.quantity,
        reservation_token=token,
    )


@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=201,
)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
):
    # 1. Fast path: return an existing order for an idempotent retry.
    existing_order = (
        db.query(Order)
        .filter(Order.idempotency_key == data.idempotency_key)
        .first()
    )

    if existing_order:
        if (
            existing_order.product_id != data.product_id
            or existing_order.quantity != data.quantity
        ):
            raise HTTPException(
                status_code=409,
                detail="Idempotency key already used for a different order",
            )

        # The retry may have created a separate reservation.
        safe_release(data.product_id, data.reservation_token)
        return existing_order

    # 2. Claim the temporary Redis reservation.
    claimed = claim_reservation(
        data.product_id,
        data.quantity,
        data.reservation_token,
    )

    if not claimed:
        raise HTTPException(
            status_code=409,
            detail="Invalid, expired, or already-used reservation",
        )

    commit_started = False
    commit_succeeded = False

    try:
        # 3. PostgreSQL is the final inventory safeguard.
        result = db.execute(
            update(Product)
            .where(
                Product.id == data.product_id,
                Product.stock >= data.quantity,
            )
            .values(stock=Product.stock - data.quantity)
        )

        if result.rowcount == 0:
            db.rollback()
            safe_release(data.product_id, data.reservation_token)

            product = db.get(Product, data.product_id)

            if product is None:
                raise HTTPException(
                    status_code=404,
                    detail="Product not found",
                )

            raise HTTPException(
                status_code=409,
                detail="Insufficient stock",
            )

        # 4. Create the order in the same PostgreSQL transaction.
        order = Order(
            product_id=data.product_id,
            quantity=data.quantity,
            status="pending",
            idempotency_key=data.idempotency_key,
        )

        db.add(order)

        commit_started = True
        db.commit()
        commit_succeeded = True

        # 5. Refresh the committed order.
        db.refresh(order)

    except IntegrityError:
        db.rollback()

        # A concurrent request may have inserted this idempotency key.
        existing_order = (
            db.query(Order)
            .filter(Order.idempotency_key == data.idempotency_key)
            .first()
        )

        safe_release(data.product_id, data.reservation_token)

        if existing_order:
            if (
                existing_order.product_id != data.product_id
                or existing_order.quantity != data.quantity
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency key already used for a different order",
                )

            return existing_order

        raise HTTPException(
            status_code=409,
            detail="Order could not be created; please retry",
        )

    except HTTPException:
        raise

    except Exception as exc:
        print("ORDER ERROR:", repr(exc))
        db.rollback()

        # Once commit has started, its outcome might be uncertain if
        # the database connection fails. Do not blindly restore the
        # Redis reservation in that situation.
        if not commit_started:
            safe_unclaim(data.product_id, data.reservation_token)

        raise

    finally:
        db.close()

    # A successful commit must never be undone logically just because
    # Redis cleanup fails. A retry can find the committed order.
    if commit_succeeded:
        invalidate_products_cache()
        safe_release(data.product_id, data.reservation_token)

    return order
