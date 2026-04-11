# app/routes/password_routes.py
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException, status, Depends
from app.models.otp_model import ForgotPasswordRequest, OTPVerify, ResetPasswordRequest
from app.services.otp_service import OTPService
from app.services.user_service import UserService
from app.db.mongodb import get_database
from app.core.security import get_password_hash

router = APIRouter(prefix="/password", tags=["Quên mật khẩu"])

@router.post("/verify-otp")
async def verify_otp(
    request: OTPVerify,
    db = Depends(get_database)
):
    """
    Xác thực mã OTP (không đánh dấu đã dùng)
    """
    otp_service = OTPService(db)
    
    # Xác thực OTP nhưng KHÔNG đánh dấu đã sử dụng
    is_valid = await otp_service.verify_otp(
        request.email, 
        request.otp_code, 
        request.otp_type,
        mark_used=False  # Quan trọng: không đánh dấu đã dùng
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không hợp lệ hoặc đã hết hạn"
        )
    
    return {"message": "OTP xác thực thành công"}

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db = Depends(get_database)
):
    """
    Gửi OTP đến email để đặt lại mật khẩu
    """
    user_service = UserService(db)
    otp_service = OTPService(db)
    
    # Kiểm tra email có tồn tại không
    user = await user_service.get_user_by_email(request.email)
    if not user:
        # Vì lý do bảo mật, vẫn trả về thành công
        return {"message": "Nếu email tồn tại, bạn sẽ nhận được mã OTP"}
    
    # Gửi OTP
    try:
        await otp_service.send_forgot_password_otp(request.email)
        return {"message": "Mã OTP đã được gửi đến email của bạn"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể gửi email. Vui lòng thử lại sau."
        )

@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db = Depends(get_database)
):
    """
    Xác thực OTP và đặt lại mật khẩu mới
    """
    user_service = UserService(db)
    otp_service = OTPService(db)
   
    # Kiểm tra email có tồn tại không
    user = await user_service.get_user_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người dùng với email này"
        )
   
    # Xác thực OTP và đánh dấu đã sử dụng
    is_valid = await otp_service.verify_otp(
        request.email,
        request.otp_code,
        "forgot_password",
        mark_used=True  # Đánh dấu OTP đã dùng
    )
   
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không hợp lệ hoặc đã hết hạn"
        )
   
    # ====================== FIX CHÍNH ======================
    # Xử lý _id (có thể là string hoặc ObjectId)
    user_id = user["_id"]
    if isinstance(user_id, str):
        user_id = ObjectId(user_id)

    hashed_password = get_password_hash(request.new_password)
    
    result = await db["users"].update_one(
        {"_id": user_id},
        {"$set": {
            "hashed_password": hashed_password,
            "updated_at": datetime.utcnow()
        }}
    )
    
    # Debug - Xem kết quả update (rất quan trọng)
    print(f"[DEBUG] Password reset - Modified count: {result.modified_count} | User ID: {user_id}")
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=500,
            detail="Không thể cập nhật mật khẩu (không tìm thấy user trong DB)"
        )
    
    return {"message": "Đặt lại mật khẩu thành công"}