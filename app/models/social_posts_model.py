from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# =========================
# ENUM / CONSTANT
# =========================
PostVisibility = Literal["public", "friends", "private"]
PostType = Literal[
    "text",        # Bài viết thường
    "product",     # Bài viết gắn sản phẩm
    "review",      # Đánh giá
    "share",       # Chia sẻ bài khác
    "system"       # Bài hệ thống
]

CategoryType = Literal[
    "agriculture", # Nông sản
    "seafood",     # Hải sản
    "specialty",   # Đặc sản
    "general"      # Chung/Khác
]

# =========================
# Base Model
# =========================
class SocialPostBase(BaseModel):
    content: Optional[str] = Field(
        None,
        description="Nội dung bài viết"
    )

    images: List[str] = Field(
        default_factory=list,
        description="Danh sách URL ảnh"
    )

    videos: List[str] = Field(
        default_factory=list,
        description="Danh sách URL video"
    )

    tags: List[str] = Field(
        default_factory=list,
        description="Hashtag / keyword tìm kiếm"
    )

    location: Optional[str] = None

    visibility: Optional[PostVisibility] = Field(
        default="public",
        description="Độ hiển thị của bài viết")

    post_type: PostType = "text"

    product_category: Optional[CategoryType] = Field(
        default="general",
        description="Loại sản phẩm: nông sản / hải sản / đặc sản"
    )
    allow_comment: bool = True
    allow_share: bool = True

# =========================
# Create Post
# =========================
class SocialPostCreate(SocialPostBase):
    author_type: Literal["admin", "user", "shop"] = "user"

    # Gắn sản phẩm (nếu là post quảng bá)
    product_id: Optional[str] = None

    # Chia sẻ bài khác
    shared_post_id: Optional[str] = None

# =========================
# Update Post
# =========================
class SocialPostUpdate(BaseModel):
    content: Optional[str] = None
    images: Optional[List[str]] = None
    videos: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    location: Optional[str] = None
    visibility: Optional[PostVisibility] = None

    allow_comment: Optional[bool] = None
    allow_share: Optional[bool] = None

    is_active: Optional[bool] = None
    is_pinned: Optional[bool] = None

# =========================
# Interaction Stats
# =========================
class SocialPostStats(BaseModel):
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    save_count: int = 0
    view_count: int = 0

# =========================
# AI / Moderation
# =========================
class SocialPostAI(BaseModel):
    sentiment: Optional[str] = None      # positive / neutral / negative
    topics: List[str] = Field(default_factory=list)
    is_spam: bool = False
    is_sensitive: bool = False

# =========================
# In Database (MongoDB)
# =========================
class SocialPostInDB(SocialPostBase):
    id: str = Field(alias="_id")

    author_id: str
    author_type: str

    product_id: Optional[str] = None
    shared_post_id: Optional[str] = None

    stats: SocialPostStats = Field(default_factory=SocialPostStats)

    ai: Optional[SocialPostAI] = None

    is_active: bool = True
    is_approved: bool = True
    is_pinned: bool = False

    report_count: int = 0

    feed_score: float = 0.0  # dùng cho ranking feed
    deleted_at: Optional[datetime] = None
    is_permanently_deleted: bool = False 
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
# =========================
# Response Model
# =========================
class SocialPostResponse(SocialPostInDB):
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None

    product_name: Optional[str] = None
    shop_name: Optional[str] = None
