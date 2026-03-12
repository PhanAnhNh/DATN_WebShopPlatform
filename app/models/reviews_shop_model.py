from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ShopReviewCreate(BaseModel):

    shop_id: str
    rating: int = Field(..., ge=1, le=5)

    comment: Optional[str] = None


class ShopReviewResponse(BaseModel):

    id: str = Field(alias="_id")

    shop_id: str
    user_id: str

    rating: int
    comment: Optional[str] = None

    created_at: datetime

    class Config:
        populate_by_name = True