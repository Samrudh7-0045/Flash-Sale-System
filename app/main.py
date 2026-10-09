
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, Product
from app.redis_client import redis_client
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
    return {"message": "Flash-Sale System is running"}


@app.get("/products", response_model=list[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()


@app.post("/reservations", response_model=ReservationResponse, status_code=201)
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



@app.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
):
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

    claimed = claim_reservation(
        data.product_id, data.quantity, data.reservation_token
    )

    if not claimed:
        raise HTTPException(
            status_code=409,
            detail="Invalid, expired, or already-used reservation",
        )

    try:
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
                raise HTTPException(status_code=404, detail="Product not found")

            raise HTTPException(status_code=409, detail="Insufficient stock")

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

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        unclaim_reservation(data.product_id, data.reservation_token)
        raise
