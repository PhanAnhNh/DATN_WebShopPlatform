from pydantic import BaseModel
from typing import List, Optional

class CartItem(BaseModel):

    product_id: str
    quantity: int
    shop_id: Optional[str] = None