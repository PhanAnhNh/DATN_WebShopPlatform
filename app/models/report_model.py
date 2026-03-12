from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from bson import ObjectId


class Report(BaseModel):

    id: Optional[str]

    reporter_id: str

    target_type: str
    # post | product | shop

    target_id: str

    reason: str

    description: Optional[str] = None

    status: str = "pending"
    # pending | reviewing | resolved | rejected

    created_at: datetime = datetime.utcnow()