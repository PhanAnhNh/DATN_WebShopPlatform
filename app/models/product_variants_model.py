from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime


class ProductVariantBase(BaseModel):

    product_id: str

    name: str = Field(..., min_length=1, max_length=100)
    # ví dụ: "Size M - Màu đỏ"

    price: float = Field(..., gt=0)

    stock: int = Field(default=0, ge=0)

    sku: Optional[str] = None

    image_url: Optional[HttpUrl] = None


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantUpdate(BaseModel):

    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    sku: Optional[str] = None
    image_url: Optional[HttpUrl] = None


class ProductVariantResponse(ProductVariantBase):

    id: str = Field(alias="_id")

    created_at: datetime

    class Config:
        populate_by_name = True