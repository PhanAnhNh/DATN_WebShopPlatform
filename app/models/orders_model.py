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

class StatusUpdateRequest(BaseModel):
    status: OrderStatus

class OrderItem(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)
    shop_id: str
    variant_id: Optional[str] = None
    variant_name: Optional[str] = None
    subtotal: Optional[float] = None

class ShippingAddress(BaseModel):
    """Model for shipping address"""
    name: str
    phone: str
    street: str
    ward: str
    district: str
    city: str
    country: str = "Việt Nam"
    full_address: Optional[str] = None

class VoucherInfo(BaseModel):
    """Model for voucher information"""
    id: str
    code: str
    discount: float

class OrderCreate(BaseModel):
    items: List[OrderItem]
    total_amount: float = Field(..., gt=0)
    subtotal: float = Field(..., gt=0)
    discount: float = Field(default=0)
    shipping_fee: float = Field(default=0)
    shipping_address: ShippingAddress  # Now accepts object instead of string
    note: Optional[str] = ""
    payment_method: str = "cod"
    voucher: Optional[VoucherInfo] = None