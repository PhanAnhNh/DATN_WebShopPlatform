from datetime import datetime
from pydantic import BaseModel

class SavedPost(BaseModel):

    user_id: str
    post_id: str
    created_at: datetime