# app/core/security.py
from datetime import datetime, timedelta
from typing import Any, Union, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.db.mongodb import get_database
from bson import ObjectId

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# Tạo class User đơn giản để trả về
class CurrentUser:
    def __init__(self, user_data: dict):
        self.id = user_data.get("_id")
        self.username = user_data.get("username")
        self.email = user_data.get("email")
        self.full_name = user_data.get("full_name")
        self.phone = user_data.get("phone")
        self.address = user_data.get("address")
        self.role = user_data.get("role", "user")
        self.shop_id = user_data.get("shop_id")
        self.default_address_id = user_data.get("default_address_id")
        self.avatar_url = user_data.get("avatar_url")
        self.cover_url = user_data.get("cover_url")
        self.gender = user_data.get("gender")
        self.dob = user_data.get("dob")
        self.is_active = user_data.get("is_active", True)
        self.is_verified = user_data.get("is_verified", False)
        self.followers_count = user_data.get("followers_count", 0)
        self.following_count = user_data.get("following_count", 0)
        self.posts_count = user_data.get("posts_count", 0)
        self.created_at = user_data.get("created_at")
        self.updated_at = user_data.get("updated_at")
        self.last_login = user_data.get("last_login")
        
        # Lưu toàn bộ dữ liệu gốc để tiện sử dụng
        self.raw = user_data

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db = Depends(get_database)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Truy vấn DB
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception
    
    # Chuyển đổi ObjectId thành string
    user["_id"] = str(user["_id"])
    if "shop_id" in user and user["shop_id"]:
        user["shop_id"] = str(user["shop_id"])
    if "default_address_id" in user and user["default_address_id"]:
        user["default_address_id"] = str(user["default_address_id"])
    
    # Trả về object có thuộc tính id
    return CurrentUser(user)

# Hàm kiểm tra role shop_owner
async def get_current_shop_owner(
    current_user: CurrentUser = Depends(get_current_user)
):
    if current_user.role != "shop_owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập. Yêu cầu tài khoản chủ shop."
        )
    
    if not current_user.shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản chưa được gắn với shop nào"
        )
    
    return current_user

# Hàm kiểm tra role admin
async def get_current_admin(
    current_user: CurrentUser = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập. Yêu cầu tài khoản admin."
        )
    
    return current_user