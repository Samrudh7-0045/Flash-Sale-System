
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

app = FastAPI(title="Flash-Sale Inventory System")


@app.get("/")
def root():
    return {"message": "Flash-Sale Inventory System is running"}


@app.get("/products", response_model=list[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()


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
    # Fast path: return an existing order for a retry.
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

        return existing_order

    # Validate and claim the temporary reservation.
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

    try:
        # Final inventory safeguard in PostgreSQL.
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
            release_stock(data.product_id, data.reservation_token)

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

        order = Order(
            product_id=data.product_id,
            quantity=data.quantity,
            status="pending",
            idempotency_key=data.idempotency_key,
        )

        db.add(order)
        db.commit()
        db.refresh(order)

        release_stock(data.product_id, data.reservation_token)

        return order

    except IntegrityError:
        # Another concurrent request may have inserted the same key.
        db.rollback()

        existing_order = (
            db.query(Order)
            .filter(Order.idempotency_key == data.idempotency_key)
            .first()
        )

        # Release this request's reservation, not the existing order's.
        release_stock(data.product_id, data.reservation_token)

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
        unclaim_reservation(data.product_id, data.reservation_token)
        raise
