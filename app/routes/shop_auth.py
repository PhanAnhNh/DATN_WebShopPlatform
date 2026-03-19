from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.services.user_service import UserService
from app.services.shop_service import ShopService
from app.core.security import create_access_token, get_current_user, verify_password
from app.core.config import settings
from app.db.mongodb import get_database
from datetime import datetime, timedelta
from bson import ObjectId

router = APIRouter(prefix="/shop/auth", tags=["Shop Authentication"])

@router.post("/login")
async def shop_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_database)
):
    """
    Đăng nhập cho chủ shop
    """
    # Tìm user theo username hoặc email
    user = await db["users"].find_one({
        "$or": [
            {"username": form_data.username},
            {"email": form_data.username}
        ]
    })
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Kiểm tra password
    if not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Kiểm tra role (chỉ shop_owner mới được đăng nhập)
    if user["role"] != "shop_owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản không phải là chủ shop"
        )
    
    # Kiểm tra shop có tồn tại không
    if not user.get("shop_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản chưa được gắn với shop nào"
        )
    
    # Lấy thông tin shop
    shop = await db["shops"].find_one({"_id": ObjectId(user["shop_id"])})
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thông tin shop"
        )
    
    # Kiểm tra trạng thái shop
    if shop.get("status") == "banned":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Shop đã bị khóa"
        )
    
    # Cập nhật last_login
    await db["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    # Tạo access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user["_id"]),
        expires_delta=access_token_expires
    )
    
    # Trả về thông tin
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"],
            "full_name": user.get("full_name"),
            "role": user["role"],
            "avatar_url": user.get("avatar_url"),
            "phone": user.get("phone")
        },
        "shop": {
            "id": str(shop["_id"]),
            "name": shop["name"],
            "slug": shop["slug"],
            "logo_url": shop.get("logo_url"),
            "banner_url": shop.get("banner_url"),
            "status": shop.get("status"),
            "is_verified": shop.get("is_verified", False)
        }
    }

@router.post("/logout")
async def shop_logout():
    """
    Đăng xuất (chỉ cần thông báo, client tự xóa token)
    """
    return {
        "message": "Đăng xuất thành công"
    }

@router.post("/refresh-token")
async def refresh_token(
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Làm mới token
    """
    # Kiểm tra role
    if current_user.role != "shop_owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập"
        )
    
    # Tạo token mới
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(current_user.id),
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }