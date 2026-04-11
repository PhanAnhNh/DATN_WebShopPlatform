# app/services/otp_service.py
import random
import string
from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import HTTPException, status

from app.db.mongodb import get_database
from app.models.otp_model import OTPCreate, OTPType, OTPVerify
from app.services.email_service import EmailService

class OTPService:
    def __init__(self, db=None):
        if db is not None:
            self.db = db
            self.collection = db.otps
        else:
            self.db = get_database()
            self.collection = self.db.otps
        self.email_service = EmailService()

    def generate_otp(self) -> str:
        """Tạo OTP gồm 6 chữ số"""
        return ''.join(random.choices(string.digits, k=6))

    async def create_otp(self, email: str, otp_type: OTPType) -> str:
        """Tạo và lưu OTP mới"""
        # Xóa các OTP cũ chưa sử dụng cho email và type này
        await self.collection.delete_many({
            "email": email,
            "otp_type": otp_type,
            "is_used": False
        })

        # Tạo OTP mới
        otp_code = self.generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=5)  # OTP hết hạn sau 5 phút

        otp_data = {
            "email": email,
            "otp_code": otp_code,
            "otp_type": otp_type,
            "expires_at": expires_at,
            "is_used": False,
            "created_at": datetime.utcnow()
        }

        await self.collection.insert_one(otp_data)
        return otp_code

    async def verify_otp(self, email: str, otp_code: str, otp_type: OTPType, mark_used: bool = False) -> bool:
        """
        Xác thực OTP
        
        Args:
            email: Email người dùng
            otp_code: Mã OTP
            otp_type: Loại OTP
            mark_used: Có đánh dấu đã sử dụng ngay không
        """
        # Tìm OTP hợp lệ
        otp = await self.collection.find_one({
            "email": email,
            "otp_code": otp_code,
            "otp_type": otp_type,
            "is_used": False,
            "expires_at": {"$gt": datetime.utcnow()}
        })

        if not otp:
            return False

        # Chỉ đánh dấu đã sử dụng nếu yêu cầu
        if mark_used:
            await self.collection.update_one(
                {"_id": otp["_id"]},
                {"$set": {"is_used": True}}
            )

        return True

    async def mark_otp_as_used(self, email: str, otp_code: str, otp_type: OTPType) -> bool:
        """Đánh dấu OTP đã được sử dụng"""
        result = await self.collection.update_one(
            {
                "email": email,
                "otp_code": otp_code,
                "otp_type": otp_type,
                "is_used": False
            },
            {"$set": {"is_used": True}}
        )
        return result.modified_count > 0

    async def send_forgot_password_otp(self, email: str) -> str:
        """Gửi OTP quên mật khẩu qua email"""
        otp_code = await self.create_otp(email, OTPType.forgot_password)
        
        # Gửi email
        await self.email_service.send_forgot_password_email(email, otp_code)
        
        return otp_code