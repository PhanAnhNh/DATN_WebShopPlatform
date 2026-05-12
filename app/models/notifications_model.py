from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class NotificationType(str, Enum):
    ORDER = "order"
    PAYMENT = "payment"
    SHIPPING = "shipping"
    SYSTEM = "system"
    PROMOTION = "promotion"
    REVIEW = "review"
    FOLLOW = "follow"
    FRIEND_REQUEST = "friend_request"  # Thêm type này
    FRIEND_ACCEPTED = "friend_accepted"  # Thêm type này

class Notification(BaseModel):
    user_id: str
    type: NotificationType
    reference_id: Optional[str] = None
    title: str  # Thêm title cho thông báo
    message: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    image_url: Optional[str] = None  # Thêm ảnh đại diện cho thông báo

class NotificationCreate(BaseModel):
    type: NotificationType
    reference_id: Optional[str] = None
    title: str
    message: str
    image_url: Optional[str] = None

class NotificationUpdate(BaseModel):
    is_read: bool

class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: NotificationType
    reference_id: Optional[str]
    title: str
    message: str
    is_read: bool
    created_at: datetime
    image_url: Optional[str]