from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Đánh giá sao từ 1-5")
    comment: Optional[str] = Field(None, max_length=1000)
    images: List[str] = Field(default_factory=list, description="Hình ảnh đánh giá")

class ReviewCreate(ReviewBase):
    pass

class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)
    images: Optional[List[str]] = None

class ReviewResponse(ReviewBase):
    id: str = Field(alias="_id")
    product_id: str
    user_id: str
    user_name: str
    user_avatar: Optional[str] = None
    status: ReviewStatus = ReviewStatus.PENDING
    helpful_count: int = 0
    created_at: datetime
    updated_at: datetime
    reply: Optional[str] = None
    reply_at: Optional[datetime] = None

    class Config:
        populate_by_name = True

class ReviewStats(BaseModel):
    average_rating: float = 0
    total_reviews: int = 0
    rating_distribution: dict = Field(default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})