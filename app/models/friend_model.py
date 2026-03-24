from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId

class FriendRequest(BaseModel):
    id: Optional[str] = None
    user_id: str  # Người gửi lời mời
    friend_id: str  # Người nhận lời mời
    status: str = "pending"  # pending, accepted, rejected, blocked
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
class FriendRequestCreate(BaseModel):
    friend_id: str  # ID của người muốn kết bạn
    
class FriendRequestUpdate(BaseModel):
    status: str  # accepted, rejected, blocked