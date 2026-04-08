# app/models/report_model.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class ReportStatus(str, Enum):
    PENDING = "pending"      # Chờ xử lý
    APPROVED = "approved"    # Đã xác nhận vi phạm
    REJECTED = "rejected"    # Từ chối báo cáo
    RESOLVED = "resolved"    # Đã xử lý xong

class ReportType(str, Enum):
    SPAM = "spam"                    # Bài viết spam
    HARASSMENT = "harassment"        # Quấy rối
    HATE_SPEECH = "hate_speech"      # Ngôn ngữ thù địch
    VIOLENCE = "violence"            # Bạo lực
    ADULT_CONTENT = "adult_content"  # Nội dung người lớn
    MISINFORMATION = "misinformation" # Thông tin sai lệch
    COPYRIGHT = "copyright"          # Vi phạm bản quyền
    OTHER = "other"                  # Khác

class ReportBase(BaseModel):
    target_type: str = "post"  # post, comment, user
    target_id: str
    report_type: ReportType
    reason: str
    description: Optional[str] = None

class ReportCreate(ReportBase):
    pass

class ReportUpdate(BaseModel):
    status: Optional[ReportStatus] = None
    admin_note: Optional[str] = None
    action_taken: Optional[str] = None

class ReportInDB(ReportBase):
    id: str = Field(alias="_id")
    reporter_id: str
    status: ReportStatus = ReportStatus.PENDING
    admin_note: Optional[str] = None
    action_taken: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

class ReportResponse(ReportInDB):
    reporter_name: Optional[str] = None
    reporter_avatar: Optional[str] = None
    target_author_name: Optional[str] = None
    target_content_preview: Optional[str] = None

class ReportStats(BaseModel):
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    resolved: int = 0