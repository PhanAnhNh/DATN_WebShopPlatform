from pydantic import BaseModel, Field
from datetime import datetime

class Message(BaseModel):

    conversation_id: str
    sender_id: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)