# app/models/return_model.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ReturnStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"
    cancelled = "cancelled"

class ReturnReason(str, Enum):
    wrong_product = "wrong_product"
    damaged = "damaged"
    expired = "expired"
    quality = "quality"
    change_mind = "change_mind"
    other = "other"

class ReturnItem(BaseModel):
    order_item_id: str
    product_id: str
    product_name: str
    variant_id: Optional[str] = None
    variant_name: Optional[str] = None
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)
    reason: ReturnReason
    reason_note: Optional[str] = None
    images: List[str] = Field(default_factory=list)

    @field_validator('quantity')
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError('Số lượng phải lớn hơn 0')
        return v

    @field_validator('price')
    def price_positive(cls, v):
        if v <= 0:
            raise ValueError('Giá phải lớn hơn 0')
        return v

class ReturnCreate(BaseModel):
    order_id: str
    items: List[ReturnItem] = Field(..., min_length=1)
    notes: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_holder: Optional[str] = None

    @field_validator('items')
    def items_not_empty(cls, v):
        if not v:
            raise ValueError('Phải có ít nhất 1 sản phẩm để hoàn trả')
        return v

class ReturnUpdate(BaseModel):
    status: Optional[ReturnStatus] = None
    admin_note: Optional[str] = None
    approved_items: Optional[List[str]] = None
    rejected_reason: Optional[str] = None
    refund_amount: Optional[float] = None
    completed_at: Optional[datetime] = None

class ReturnResponse(BaseModel):
    id: str = Field(alias="_id")
    return_code: str
    user_id: str
    user_name: Optional[str]
    user_phone: Optional[str]
    order_id: str
    order_code: str
    items: List[ReturnItem]
    total_refund: float
    status: ReturnStatus
    reason_note: Optional[str]
    admin_note: Optional[str]
    approved_items: Optional[List[str]]
    rejected_reason: Optional[str]
    refund_amount: Optional[float]
    bank_name: Optional[str]
    bank_account: Optional[str]
    bank_holder: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True