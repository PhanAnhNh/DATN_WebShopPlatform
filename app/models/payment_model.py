from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class PaymentMethod(str, Enum):
    COD = "cod"
    MOMO = "momo"
    VNPAY = "vnpay"
    ZALOPAY = "zalopay"
    BANK_TRANSFER = "bank_transfer"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentCreate(BaseModel):
    order_id: str
    method: PaymentMethod
    amount: float
    bank_code: Optional[str] = None
    card_type: Optional[str] = None

class PaymentResponse(BaseModel):
    id: str
    order_id: str
    user_id: str
    method: PaymentMethod
    amount: float
    status: PaymentStatus
    transaction_id: Optional[str]
    payment_url: Optional[str]  # URL chuyển hướng thanh toán
    created_at: datetime
    completed_at: Optional[datetime]

class MomoPaymentRequest(BaseModel):
    order_id: str
    amount: float
    order_info: str

class VNPayPaymentRequest(BaseModel):
    order_id: str
    amount: float
    order_desc: str
    bank_code: Optional[str]
    language: str = "vn"