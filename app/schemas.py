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

class OrderResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    status: str

    model_config = {"from_attributes": True}


class ReservationCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class ReservationResponse(BaseModel):
    product_id: int
    quantity: int
    reservation_token: str
    expires_in_seconds: int = 60


class OrderCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    reservation_token: str
    idempotency_key: str = Field(min_length=1, max_length=100)