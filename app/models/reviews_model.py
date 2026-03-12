from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ProductReviewCreate(BaseModel):

    product_id: str
    rating: int = Field(..., ge=1, le=5)

    comment: Optional[str] = None
    image_url: Optional[str] = None


class ProductReviewResponse(BaseModel):

    id: str = Field(alias="_id")

    product_id: str
    user_id: str

    rating: int
    comment: Optional[str] = None
    image_url: Optional[str] = None

    created_at: datetime

    class Config:
        populate_by_name = True