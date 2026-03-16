from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date, datetime
from bson import ObjectId

class ShopBase(BaseModel):
    name: str = Field(..., min_length=3)
    slug: str = Field(..., description="URL thân thiện")
    description: Optional[str] = None

    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None

    logo_url: Optional[str] = None
    banner_url: Optional[str] = None

class ShopCreate(ShopBase):
    pass

class ShopWithOwnerCreate(BaseModel):
    # Thông tin shop
    shop_name: str = Field(..., min_length=3)
    shop_slug: str = Field(..., description="URL thân thiện")
    shop_description: Optional[str] = None
    shop_phone: Optional[str] = None
    shop_email: Optional[str] = None
    shop_address: Optional[str] = None
    shop_province: Optional[str] = None
    shop_district: Optional[str] = None
    shop_ward: Optional[str] = None
    shop_logo_url: Optional[str] = None
    shop_banner_url: Optional[str] = None
    
    # Thông tin chủ shop
    owner_username: str = Field(..., min_length=3)
    owner_email: EmailStr
    owner_password: str = Field(..., min_length=6)
    owner_full_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_gender: Optional[str] = None
    owner_dob: Optional[date] = None
    owner_address: Optional[str] = None

class ShopUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    status: Optional[str] = None

class ShopInDB(ShopBase):
    id: str = Field(alias="_id")
    owner_id: str

    status: str = "active"        # active | inactive | banned
    is_verified: bool = False

    products_count: int = 0
    posts_count: int = 0
    followers_count: int = 0
    total_orders: int = 0
    total_revenue: float = 0
    view_count: int = 0

    created_at: datetime
    updated_at: datetime