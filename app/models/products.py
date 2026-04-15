# app/models/products.py
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime

from app.models.product_variants_model import ProductVariantResponse, ProductVariantCreateWithProduct

class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    category_id: str
    origin: Optional[str] = None
    image_url: Optional[str] = None
    has_traceability: bool = Field(default=False)
    traceability_id: Optional[str] = None

class ProductCreate(ProductBase):
    variants: List[ProductVariantCreateWithProduct] = Field(default_factory=list)
    price: Optional[float] = None  
    stock: Optional[int] = 0       

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    origin: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None

class ProductResponse(ProductBase):
    id: str = Field(alias="_id")
    shop_id: str
    qr_code_url: Optional[str] = None
    variants: list[ProductVariantResponse] = Field(default_factory=list)
    created_at: datetime
    price: Optional[float] = None
    stock: Optional[int] = 0

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True