from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class PostLike(BaseModel):
    post_id: str
    user_id: str

    created_at: datetime = Field(default_factory=datetime.utcnow)