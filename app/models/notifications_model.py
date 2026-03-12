from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class Notification(BaseModel):
    user_id: str
    type: str
    reference_id: Optional[str] = None
    message: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)