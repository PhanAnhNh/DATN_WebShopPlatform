# app/models/save_model.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class SavedPostBase(BaseModel):
    """Model cơ bản cho bài viết đã lưu"""
    post_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    note: Optional[str] = Field(None, max_length=500, description="Ghi chú cho bài viết đã lưu")

class SavedPostCreate(BaseModel):
    """Tạo bài viết đã lưu"""
    post_id: str
    note: Optional[str] = None

class SavedPostResponse(SavedPostBase):
    """Response bài viết đã lưu"""
    id: str = Field(alias="_id")
    
    class Config:
        populate_by_name = True

class SavedPostWithDetails(SavedPostResponse):
    """Bài viết đã lưu kèm thông tin chi tiết của post"""
    post: Optional[dict] = None