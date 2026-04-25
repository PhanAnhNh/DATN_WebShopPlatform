# app/routes/auth_routes.py
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.services.user_service import UserService
from app.core.security import get_current_user, verify_password, create_access_token, CurrentUser
from datetime import timedelta
from app.core.config import settings
from app.db.mongodb import get_database
from bson import ObjectId

router = APIRouter(prefix="/auth", tags=["Xác thực (Login)"])


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_database)
):
    user_service = UserService(db)
    user = await user_service.get_user_by_username(form_data.username)
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Tài khoản hoặc mật khẩu không chính xác")

    access_token = create_access_token(
        subject=str(user["_id"]), 
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Trả về access_token và thông tin user
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "username": user.get("username", ""),
            "full_name": user.get("full_name", ""),
            "avatar_url": user.get("avatar_url", ""),
            "cover_url": user.get("cover_url", ""),
            "email": user.get("email", ""),
            "gender": user.get("gender", ""),
            "phone": user.get("phone", ""),
            "address": user.get("address", ""),
            "dob": user.get("dob").isoformat() if user.get("dob") else None,
            "role": user.get("role", "user"),
            "default_address_id": user.get("default_address_id"),
            "is_active": user.get("is_active", True),
            "is_verified": user.get("is_verified", False),
            "followers_count": user.get("followers_count", 0),
            "following_count": user.get("following_count", 0),
            "posts_count": user.get("posts_count", 0),
            "shop_id": user.get("shop_id"),
            "created_at": user.get("created_at").isoformat() if user.get("created_at") else None,
            "updated_at": user.get("updated_at").isoformat() if user.get("updated_at") else None
        }
    }


@router.get("/me")
async def get_my_profile(
    current_user: CurrentUser = Depends(get_current_user),  # SỬA: thêm type hint CurrentUser
    db = Depends(get_database)
):
    """
    Lấy thông tin của người dùng đang đăng nhập dựa vào Token
    """
    # Lấy thêm thông tin địa chỉ mặc định nếu có
    from app.services.address_service import AddressService
    address_service = AddressService(db)
    
    default_address = None
    if current_user.default_address_id:
        default_address = await address_service.get_address_by_id(
            current_user.default_address_id, 
            current_user.id
        )
    
    # Tạo dict trả về
    user_data = {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "address": current_user.address,
        "gender": current_user.gender,
        "dob": current_user.dob.isoformat() if current_user.dob else None,
        "role": current_user.role,
        "avatar_url": current_user.avatar_url,
        "cover_url": current_user.cover_url,
        "shop_id": current_user.shop_id,
        "default_address_id": current_user.default_address_id,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "followers_count": current_user.followers_count,
        "following_count": current_user.following_count,
        "posts_count": current_user.posts_count,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None
    }
    
    # Thêm thông tin địa chỉ mặc định
    if default_address:
        user_data["default_address"] = default_address
    
    return user_data


@router.put("/update-profile")
async def update_profile(
    profile_data: dict,
    db = Depends(get_database),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Cập nhật thông tin người dùng (không bao gồm địa chỉ)
    """
    from app.models.user_model import UserUpdate
    user_service = UserService(db)
    
    # THÊM "email" vào allowed_fields
    allowed_fields = ["full_name", "phone", "gender", "dob", "avatar_url", "cover_url", "email", "address"]
    update_dict = {k: v for k, v in profile_data.items() if k in allowed_fields and v is not None}
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    # Kiểm tra email không bị trùng với người dùng khác
    if "email" in update_dict:
        existing_user = await user_service.get_user_by_email(update_dict["email"])
        if existing_user and existing_user["id"] != current_user.id:
            raise HTTPException(status_code=400, detail="Email đã được sử dụng bởi tài khoản khác")
    
    user_update = UserUpdate(**update_dict)
    success = await user_service.update_user(current_user.id, user_update)
    
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Lấy lại thông tin user sau khi cập nhật
    updated_user = await user_service.get_user_by_id(current_user.id)
    if updated_user:
        updated_user.pop("hashed_password", None)
        # Đảm bảo có id
        if "_id" in updated_user:
            updated_user["id"] = str(updated_user["_id"])
    
    return {"message": "Profile updated successfully", "user": updated_user}