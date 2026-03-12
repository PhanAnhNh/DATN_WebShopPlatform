from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
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