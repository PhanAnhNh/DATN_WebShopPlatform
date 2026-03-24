from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class PostCommentBase(BaseModel):
    content: str = Field(..., min_length=1, description="Nội dung bình luận")
    image_url: Optional[str] = None 

class PostCommentCreate(PostCommentBase):
    post_id: str
    parent_id: Optional[str] = None

class PostCommentUpdate(BaseModel):
    content: Optional[str] = None
    image_url: Optional[str] = None    

class PostCommentResponse(PostCommentBase):
    id: str = Field(alias="_id")
    post_id: str
    user_id: str  # Thêm user_id
    author_id: Optional[str] = None  # Thêm author_id để tương thích
    parent_id: Optional[str] = None
    
    # Thông tin người dùng để hiện lên giao diện
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True