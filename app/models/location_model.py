# app/models/location.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId
from app.schemas.base import PyObjectId

class Location(BaseModel):
    """Địa điểm cụ thể (cửa hàng, điểm đến)"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    name: str = Field(..., description="Tên địa điểm")
    description: Optional[str] = Field(None, description="Mô tả")
    address: str = Field(..., description="Địa chỉ chi tiết")
    lat: float = Field(..., description="Vĩ độ")
    lng: float = Field(..., description="Kinh độ")
    province_id: str = Field(..., description="ID tỉnh/thành")
    province_name: str = Field(..., description="Tên tỉnh/thành")
    district: Optional[str] = Field(None, description="Quận/huyện")
    ward: Optional[str] = Field(None, description="Phường/xã")
    phone: Optional[str] = Field(None, description="Số điện thoại")
    email: Optional[str] = Field(None, description="Email")
    website: Optional[str] = Field(None, description="Website")
    opening_hours: Optional[str] = Field(None, description="Giờ mở cửa")
    images: List[str] = Field(default_factory=list, description="Hình ảnh")
    category: str = Field(default="store", description="Phân loại: store, tourist_spot, restaurant")
    rating: float = Field(default=0, ge=0, le=5)
    total_reviews: int = Field(default=0)
    status: str = Field(default="active", description="active, inactive")
    created_by: Optional[str] = Field(None, description="Người tạo")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class Province(BaseModel):
    """Tỉnh/Thành phố"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    name: str = Field(..., description="Tên tỉnh/thành")
    name_en: Optional[str] = Field(None, description="Tên tiếng Anh")
    code: str = Field(..., description="Mã tỉnh (VD: 01, 02...)")
    region: Optional[str] = Field(None, description="Miền: North, Central, South")
    center_lat: Optional[float] = Field(None, description="Tọa độ trung tâm")
    center_lng: Optional[float] = Field(None, description="Tọa độ trung tâm")
    image_url: Optional[str] = Field(None, description="Hình ảnh đại diện")
    description: Optional[str] = Field(None, description="Mô tả")
    population: Optional[int] = Field(None, description="Dân số")
    area: Optional[float] = Field(None, description="Diện tích")
    status: str = Field(default="active", description="active, inactive")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class District(BaseModel):
    """Quận/Huyện"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    name: str = Field(..., description="Tên quận/huyện")
    code: str = Field(..., description="Mã quận/huyện")
    province_id: str = Field(..., description="ID tỉnh/thành")
    province_name: str = Field(..., description="Tên tỉnh/thành")
    center_lat: Optional[float] = Field(None)
    center_lng: Optional[float] = Field(None)
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}