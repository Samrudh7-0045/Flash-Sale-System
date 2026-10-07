from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product
from app.schemas import ProductResponse

app = FastAPI(title="Flash-Sale Inventory System")


@app.get("/")
def root():
    return {"message": "Flash-Sale System is running"}


@app.get("/products", response_model=list[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()