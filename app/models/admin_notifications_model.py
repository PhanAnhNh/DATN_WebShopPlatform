# app/models/admin_notifications_model.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class AdminNotificationType(str, Enum):
    NEW_USER = "new_user"           # Người dùng mới đăng ký
    NEW_SHOP = "new_shop"           # Cửa hàng mới đăng ký
    NEW_POST = "new_post"           # Bài viết mới
    REPORT_USER = "report_user"     # Báo cáo người dùng
    REPORT_SHOP = "report_shop"     # Báo cáo cửa hàng
    REPORT_POST = "report_post"     # Báo cáo bài viết
    SYSTEM = "system"               # Thông báo hệ thống

class AdminNotification(BaseModel):
    user_id: str  # ID của admin (có thể có nhiều admin)
    type: AdminNotificationType
    reference_id: Optional[str] = None
    title: str
    message: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    image_url: Optional[str] = None

class AdminNotificationCreate(BaseModel):
    type: AdminNotificationType
    reference_id: Optional[str] = None
    title: str
    message: str
    image_url: Optional[str] = None

class AdminNotificationResponse(BaseModel):
    id: str
    user_id: str
    type: AdminNotificationType
    reference_id: Optional[str]
    title: str
    message: str
    is_read: bool
    created_at: datetime
    image_url: Optional[str]