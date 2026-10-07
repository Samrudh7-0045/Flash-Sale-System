from decimal import Decimal

from pydantic import BaseModel


class ProductResponse(BaseModel):
    id: int
    name: str
    price: Decimal
    stock: int

    model_config = {
        "from_attributes": True
    }