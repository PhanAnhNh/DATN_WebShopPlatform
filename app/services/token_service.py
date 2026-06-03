# app/services/token_service.py
import secrets
from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId

class VerificationTokenService:
    def __init__(self, db):
        self.db = db
        self.collection = db.verification_tokens
    
    async def create_verification_token(self, user_id: str) -> str:
        """Tạo token xác thực cho user"""
        token = secrets.token_urlsafe(32)
        
        # Xóa token cũ nếu có
        await self.collection.delete_many({"user_id": user_id})
        
        # Tạo token mới
        token_data = {
            "user_id": user_id,
            "token": token,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=24),  # Hết hạn sau 24h
            "used": False
        }
        
        await self.collection.insert_one(token_data)
        return token
    
    async def verify_token(self, token: str) -> Optional[dict]:
        """Xác thực token và trả về user_id nếu hợp lệ"""
        token_data = await self.collection.find_one({
            "token": token,
            "used": False,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if not token_data:
            return None
        
        # Đánh dấu token đã được sử dụng
        await self.collection.update_one(
            {"_id": token_data["_id"]},
            {"$set": {"used": True}}
        )
        
        return token_data
    
    async def delete_expired_tokens(self):
        """Xóa các token đã hết hạn"""
        await self.collection.delete_many({
            "expires_at": {"$lt": datetime.utcnow()}
        })