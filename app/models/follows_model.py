from pydantic import BaseModel
from datetime import datetime

class Follow(BaseModel):
    follower_id: str
    following_id: str
    created_at: datetime

class FollowResponse(BaseModel):
    following: bool