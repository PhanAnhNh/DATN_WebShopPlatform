# app/models/group_model.py
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum

class GroupPrivacy(str, Enum):
    PUBLIC = "public"      # Công khai - ai cũng thấy bài viết
    PRIVATE = "private"    # Riêng tư - chỉ thành viên thấy

class GroupRole(str, Enum):
    ADMIN = "admin"        # Quản trị viên
    MEMBER = "member"      # Thành viên
    PENDING = "pending"    # Đang chờ duyệt

class GroupMember(BaseModel):
    user_id: str
    role: GroupRole = GroupRole.PENDING
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    added_by: Optional[str] = None  # Ai đã thêm (cho thành viên được mời)

class GroupPost(BaseModel):
    post_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class GroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    privacy: GroupPrivacy = GroupPrivacy.PUBLIC
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None

class GroupCreate(GroupBase):
    pass

class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    privacy: Optional[GroupPrivacy] = None
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None

class GroupInDB(GroupBase):
    id: str = Field(alias="_id")
    owner_id: str  # Người tạo nhóm
    members: List[GroupMember] = Field(default_factory=list)
    posts: List[GroupPost] = Field(default_factory=list)
    post_count: int = 0
    member_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    is_active: bool = True

class GroupResponse(GroupInDB):
    owner_name: Optional[str] = None
    owner_avatar: Optional[str] = None
    user_role: Optional[str] = None  # Vai trò của user hiện tại trong nhóm