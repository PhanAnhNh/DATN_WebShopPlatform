# app/schemas/locations.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class LocationBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    description: Optional[str] = None
    address: str
    lat: float
    lng: float
    province_id: str
    province_name: str
    district: Optional[str] = None
    ward: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[str] = None
    images: List[str] = []
    category: str = "store"
    rating: float = 0
    total_reviews: int = 0

class LocationCreate(LocationBase):
    pass

class LocationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    province_id: Optional[str] = None
    province_name: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[str] = None
    images: Optional[List[str]] = None
    category: Optional[str] = None
    status: Optional[str] = None

class ProvinceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    name: str
    name_en: Optional[str] = None
    code: str
    region: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    population: Optional[int] = None
    area: Optional[float] = None

class ProvinceCreate(ProvinceBase):
    pass

class ProvinceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = None
    name_en: Optional[str] = None
    code: Optional[str] = None
    region: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    population: Optional[int] = None
    area: Optional[float] = None
    status: Optional[str] = None

class LocationFilter(BaseModel):
    province_id: Optional[str] = None
    category: Optional[str] = None
    keyword: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius: Optional[float] = Field(default=10, description="Bán kính tìm kiếm (km)")
    limit: int = 50
    page: int = 1