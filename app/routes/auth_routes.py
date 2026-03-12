from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.services.user_service import UserService
from app.core.security import get_current_user, verify_password, create_access_token
from datetime import timedelta
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Xác thực (Login)"])

# app/routes/auth_routes.py

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_service: UserService = Depends()
):
    user = await user_service.get_user_by_username(form_data.username)
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Tài khoản hoặc mật khẩu không chính xác")

    access_token = create_access_token(
        subject=str(user["_id"]), 
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # THÊM ĐOẠN NÀY: Trả về access_token VÀ thông tin user
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "username": user.get("username", ""),
            "full_name": user.get("full_name", ""),
            "avatar_url": user.get("avatar_url", ""),
            "email": user.get("email", ""),
            "gender": user.get("gender", ""),
            "phone": user.get("phone", ""),
            "address": user.get("address", ""),
            "dob": user.get("dob").isoformat() if user.get("dob") else "" # Chuyển ngày tháng thành chuỗi để Frontend dễ đọc
        }
    }

@router.get("/me")
async def get_my_profile(
    current_user: dict = Depends(get_current_user)
):
    """
    Lấy thông tin của người dùng đang đăng nhập dựa vào Token
    """
    # Xóa mật khẩu đã mã hóa trước khi trả dữ liệu về Frontend để bảo mật
    if "hashed_password" in current_user:
        current_user.pop("hashed_password")
        
    return current_user