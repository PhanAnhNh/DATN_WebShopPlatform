# app/models/return_model.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ReturnStatus(str, Enum):
    pending = "pending"        # Chờ xử lý
    approved = "approved"      # Đã duyệt
    rejected = "rejected"      # Từ chối
    completed = "completed"    # Hoàn thành
    cancelled = "cancelled"    # Đã hủy

class ReturnReason(str, Enum):
    wrong_product = "wrong_product"       # Sai sản phẩm
    damaged = "damaged"                    # Hư hỏng
    expired = "expired"                    # Hết hạn
    quality = "quality"                     # Chất lượng kém
    change_mind = "change_mind"             # Đổi ý
    other = "other"                          # Lý do khác

class ReturnItem(BaseModel):
    order_item_id: str
    product_id: str
    product_name: str
    variant_id: Optional[str] = None
    variant_name: Optional[str] = None
    quantity: int = Field(..., gt=0)
    price: float
    reason: ReturnReason
    reason_note: Optional[str] = None
    images: List[str] = []  # URL ảnh chứng minh

class ReturnCreate(BaseModel):
    order_id: str
    items: List[ReturnItem]
    notes: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_holder: Optional[str] = None

class ReturnUpdate(BaseModel):
    status: Optional[ReturnStatus] = None
    admin_note: Optional[str] = None
    approved_items: Optional[List[str]] = None  # List các item_id được duyệt
    rejected_reason: Optional[str] = None
    refund_amount: Optional[float] = None
    completed_at: Optional[datetime] = None

class ReturnResponse(BaseModel):
    id: str = Field(alias="_id")
    return_code: str  # Mã yêu cầu đổi trả (RT + datetime)
    user_id: str
    user_name: Optional[str]
    user_phone: Optional[str]
    order_id: str
    order_code: str
    items: List[ReturnItem]
    total_refund: float
    status: ReturnStatus
    reason_note: Optional[str]
    admin_note: Optional[str]
    approved_items: Optional[List[str]]
    rejected_reason: Optional[str]
    refund_amount: Optional[float]
    bank_name: Optional[str]
    bank_account: Optional[str]
    bank_holder: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True