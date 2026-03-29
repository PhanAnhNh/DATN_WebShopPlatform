# app/models/shipping_unit_model.py
from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ShippingUnitStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"

class ShippingUnitBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Tên đơn vị vận chuyển")
    code: str = Field(..., min_length=2, max_length=20, description="Mã đơn vị vận chuyển")
    logo_url: Optional[str] = None  # SỬA: thay HttpUrl bằng str
    description: Optional[str] = None
    website: Optional[str] = None  # SỬA: thay HttpUrl bằng str
    phone: Optional[str] = Field(None, pattern=r"^(0|\+84)(3|5|7|8|9)[0-9]{8}$")
    email: Optional[str] = None
    
    # Cấu hình vận chuyển
    shipping_fee_base: float = Field(default=0, ge=0, description="Phí vận chuyển cơ bản")
    free_shipping_threshold: Optional[float] = Field(None, ge=0, description="Giá trị đơn hàng tối thiểu để miễn phí ship")
    estimated_delivery_days: int = Field(default=3, ge=1, le=30, description="Số ngày dự kiến giao hàng")
    
    # Các tỉnh thành hỗ trợ
    supported_provinces: List[str] = Field(default_factory=list, description="Danh sách tỉnh/thành phố hỗ trợ")
    
    # Trạng thái
    status: ShippingUnitStatus = ShippingUnitStatus.active
    
    @field_validator('logo_url', 'website', mode='before')
    @classmethod
    def validate_url_or_none(cls, v):
        """Validate URL hoặc None"""
        if v is None or v == '':
            return None
        return v

# Model cho Shop tạo (không cần shop_id)
class ShippingUnitCreate(ShippingUnitBase):
    pass

class ShippingUnitUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    logo_url: Optional[str] = None  # SỬA: thay HttpUrl bằng str
    description: Optional[str] = None
    website: Optional[str] = None  # SỬA: thay HttpUrl bằng str
    phone: Optional[str] = None
    email: Optional[str] = None
    shipping_fee_base: Optional[float] = None
    free_shipping_threshold: Optional[float] = None
    estimated_delivery_days: Optional[int] = None
    supported_provinces: Optional[List[str]] = None
    status: Optional[ShippingUnitStatus] = None

class ShippingUnitResponse(ShippingUnitBase):
    id: str = Field(alias="_id")
    shop_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    total_orders: int = 0
    total_revenue: float = 0
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class ShippingUnitStats(BaseModel):
    unit_id: str
    unit_name: str
    unit_code: str
    total_orders: int
    total_revenue: float
    success_rate: float
    avg_delivery_days: float