from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime

from app.models.product_variants_model import ProductVariantResponse

class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    category_id: str
    origin: Optional[str] = None
    certification: Optional[str] = None
    image_url: Optional[HttpUrl] = None

class ProductCreate(ProductBase):
    # Dữ liệu khi nhận từ Client (không cần shop_id vì lấy từ Token)
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    origin: Optional[str] = None
    certification: Optional[str] = None
    image_url: Optional[HttpUrl] = None

class ProductResponse(ProductBase):
    id: str = Field(alias="_id") # Thêm alias này để Pydantic tự hiểu _id từ DB là id
    shop_id: str
    qr_code_url: Optional[str] = None
    variants: list[ProductVariantResponse] = Field(default_factory=list)
    created_at: datetime

    class Config:
        populate_by_name = True # Cho phép dùng cả 'id' và '_id'