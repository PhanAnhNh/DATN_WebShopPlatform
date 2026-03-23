from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, date
from enum import Enum

class UserRole(str, Enum):
    user = "user"
    shop_owner = "shop_owner"
    admin = "admin"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3)
    email: EmailStr
    full_name: Optional[str] = None

    phone: Optional[str] = Field(
        None, pattern=r"^(0|\+84)(3|5|7|8|9)[0-9]{8}$"
    )
    gender: Optional[str] = None
    dob: Optional[date] = None
    address: Optional[str] = None

    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None

    role: UserRole = UserRole.user
    is_active: bool = True
    is_verified: bool = False

    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0

    shop_id: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    email: EmailStr
    password: str = Field(..., min_length=6)

    full_name: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[date] = None
    address: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[date] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None
    password: Optional[str] = None


class UserInDB(UserBase):
    id: str = Field(alias="_id")
    hashed_password: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    default_address_id: Optional[str] = None