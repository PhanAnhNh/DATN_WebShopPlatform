# app/models/address_model.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AddressBase(BaseModel):
    """Model cơ bản cho địa chỉ"""
    name: str = Field(..., min_length=2, max_length=100, description="Tên người nhận")
    phone: str = Field(..., pattern=r"^(0|\+84)(3|5|7|8|9)[0-9]{8}$", description="Số điện thoại người nhận")
    
    # Chi tiết địa chỉ
    street: str = Field(..., min_length=3, description="Số nhà, tên đường")
    ward: str = Field(..., min_length=2, description="Phường/Xã")
    district: str = Field(..., min_length=2, description="Quận/Huyện")
    city: str = Field(..., min_length=2, description="Tỉnh/Thành phố")
    country: str = Field(default="Việt Nam", description="Quốc gia")
    
    # Tùy chọn
    is_default: bool = Field(default=False, description="Địa chỉ mặc định")
    address_type: Optional[str] = Field(default="home", description="Loại địa chỉ: home, office, other")
    note: Optional[str] = Field(None, description="Ghi chú thêm")


class AddressCreate(AddressBase):
    """Tạo địa chỉ mới - KHÔNG cần user_id vì sẽ lấy từ current_user"""
    pass  # Bỏ user_id


class AddressUpdate(BaseModel):
    """Cập nhật địa chỉ"""
    name: Optional[str] = None
    phone: Optional[str] = None
    street: Optional[str] = None
    ward: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    is_default: Optional[bool] = None
    address_type: Optional[str] = None
    note: Optional[str] = None


class AddressResponse(AddressBase):
    """Response địa chỉ"""
    id: str = Field(alias="_id")
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
    
    def full_address(self) -> str:
        """Trả về địa chỉ đầy đủ"""
        parts = [self.street, self.ward, self.district, self.city, self.country]
        return ", ".join(filter(None, parts))