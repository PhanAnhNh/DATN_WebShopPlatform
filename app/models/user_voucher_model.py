from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserVoucher(BaseModel):

    id: Optional[str]

    user_id: str

    voucher_id: str

    saved_at: datetime = datetime.utcnow()

    used: bool = False