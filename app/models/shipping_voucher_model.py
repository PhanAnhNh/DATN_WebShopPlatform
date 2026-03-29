# app/models/shipping_voucher_model.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ShippingVoucherStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    expired = "expired"

class ShippingVoucherType(str, Enum):
    percent = "percent"
    fixed = "fixed"

class ShippingVoucherCreate(BaseModel):
    code: str = Field(..., min_length=3, max_length=20)
    discount_type: ShippingVoucherType
    discount_value: float = Field(..., gt=0)
    max_discount: Optional[float] = Field(None, ge=0)
    min_order_value: float = Field(default=0, ge=0)
    usage_limit: Optional[int] = Field(None, gt=0)
    shipping_unit_id: str  # ID của đơn vị vận chuyển
    start_date: datetime
    end_date: datetime
    description: Optional[str] = None
    
    @field_validator('code')
    def code_uppercase(cls, v):
        return v.upper()
    
    @field_validator('end_date')
    def end_date_after_start(cls, v, info):
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

class ShippingVoucherUpdate(BaseModel):
    discount_value: Optional[float] = None
    max_discount: Optional[float] = None
    min_order_value: Optional[float] = None
    usage_limit: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[ShippingVoucherStatus] = None
    description: Optional[str] = None

class ShippingVoucherResponse(BaseModel):
    id: str = Field(alias="_id")
    code: str
    discount_type: ShippingVoucherType
    discount_value: float
    max_discount: Optional[float] = None
    min_order_value: float
    usage_limit: Optional[int] = None
    used_count: int = 0
    shipping_unit_id: str
    shipping_unit_name: Optional[str] = None
    start_date: datetime
    end_date: datetime
    status: ShippingVoucherStatus
    description: Optional[str] = None
    created_by: str  # admin | shop
    shop_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True