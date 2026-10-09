from decimal import Decimal

from pydantic import BaseModel


from decimal import Decimal

from pydantic import BaseModel, Field

class ProductResponse(BaseModel):
    id: int
    name: str
    price: Decimal
    stock: int

    model_config = {
        "from_attributes": True
    }


class ProductResponse(BaseModel):
    id: int
    name: str
    price: Decimal
    stock: int

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    status: str

    model_config = {"from_attributes": True}