# app/models/orders_model.py
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

class OrderUpdate(BaseModel):
    """Model for updating order status"""
    status: OrderStatus
    note: Optional[str] = None

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

class ShippingUnitInfo(BaseModel):
    """Model for shipping unit information"""
    id: str
    name: str
    code: str
    shipping_fee: float
    estimated_delivery_days: int

class OrderCreate(BaseModel):
    items: List[OrderItem]
    total_amount: float = Field(..., gt=0)
    subtotal: float = Field(..., gt=0)
    discount: float = Field(default=0)
    shipping_fee: float = Field(default=0)
    shipping_address: ShippingAddress
    note: Optional[str] = ""
    payment_method: str = "cod"
    voucher: Optional[VoucherInfo] = None
    shipping_unit_id: Optional[str] = None


# ✅ THÊM MODEL NÀY CHO ORDER RESPONSE
class OrderResponse(BaseModel):
    """Model for order response"""
    id: str
    order_code: str
    user_id: str
    items: List[dict]
    total_amount: float
    subtotal: float
    discount: float
    shipping_fee: float
    status: str
    payment_status: str
    payment_method: str
    shipping_address: str
    shipping_address_details: dict
    note: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    qr_code_url: Optional[str] = None  # ✅ THÊM QR CODE URL
    transaction_id: Optional[str] = None  # ✅ THÊM TRANSACTION ID
    transfer_content: Optional[str] = None