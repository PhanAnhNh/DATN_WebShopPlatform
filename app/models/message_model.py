from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class Message(BaseModel):
    id: Optional[str] = None
    sender_id: str
    receiver_id: str
    content: str
    message_type: str = "text"  # text, image, file
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MessageCreate(BaseModel):
    receiver_id: str
    content: str
    message_type: str = "text"

class MessageResponse(BaseModel):
    id: str
    sender_id: str
    receiver_id: str
    content: str
    message_type: str
    is_read: bool
    created_at: datetime
    sender_name: Optional[str] = None
    sender_avatar: Optional[str] = None