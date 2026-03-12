from pydantic import BaseModel, Field
from datetime import datetime

class PostShare(BaseModel):
    post_id: str
    user_id: str

    created_at: datetime = Field(default_factory=datetime.utcnow)