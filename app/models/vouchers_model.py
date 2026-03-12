from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Voucher(BaseModel):

    id: Optional[str]

    code: str

    discount_type: str
    # percent | fixed

    discount_value: float

    max_discount: Optional[float] = None

    min_order_value: Optional[float] = 0

    usage_limit: Optional[int] = None

    used_count: int = 0

    start_date: datetime

    end_date: datetime

    target_type: str
    # platform | shop | product

    shop_id: Optional[str] = None
    product_id: Optional[str] = None

    created_by: str
    # admin | shop

    status: str = "active"

    created_at: datetime = datetime.utcnow()