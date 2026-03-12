from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    shipped = "shipped"
    completed = "completed"
    cancelled = "cancelled"

class OrderItem(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)
    shop_id: str
    variant_id: Optional[str] = None
    variant_name: Optional[str] = None

class OrderCreate(BaseModel):
    shipping_address: str
    items: List[OrderItem]

class Order(BaseModel):

    user_id: str
    items: List[OrderItem]

    total_price: float

    status: OrderStatus = OrderStatus.pending

    shipping_address: str

    created_at: datetime = Field(default_factory=datetime.utcnow)