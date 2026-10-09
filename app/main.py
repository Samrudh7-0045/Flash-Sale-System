from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, Product
from app.schemas import OrderCreate, OrderResponse, ProductResponse

app = FastAPI(title="Flash-Sale Inventory System")


@app.get("/")
def root():
    return {"message": "Flash-Sale System is running"}


@app.get("/products", response_model=list[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()


@app.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
):
    try:
        # Deduct stock only if enough inventory exists.
        result = db.execute(
            update(Product)
            .where(
                Product.id == order_data.product_id,
                Product.stock >= order_data.quantity,
            )
            .values(stock=Product.stock - order_data.quantity)
        )

        if result.rowcount == 0:
            db.rollback()

            product = db.get(Product, order_data.product_id)

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
            product_id=order_data.product_id,
            quantity=order_data.quantity,
            status="pending",
        )

        db.add(order)
        db.commit()
        db.refresh(order)

        return order

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise
