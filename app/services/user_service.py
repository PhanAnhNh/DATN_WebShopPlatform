# app/services/user_service.py
from app.db.mongodb import get_database
from app.core.security import get_password_hash, verify_password
from app.models.user_model import UserCreate, UserUpdate
from bson import ObjectId
from datetime import datetime
from typing import Optional
from app.services import email_service
from app.services.token_service import VerificationTokenService
from app.core.config import settings
from app.services.admin_notification_service import AdminNotificationService

class UserService:
    def __init__(self, db=None):
        if db is not None:
            self.db = db
            self.collection = db.users
        else:
            self.db = get_database()
            self.collection = self.db.users
        self.email_service = email_service()
        self.token_service = VerificationTokenService(self.db)
        self.admin_notification_service = AdminNotificationService(self.db)

    async def create_user(self, user_in: UserCreate):
        user_dict = user_in.model_dump()

        if user_dict.get("dob"):
            user_dict["dob"] = datetime.combine(
                user_dict["dob"], datetime.min.time()
            )

        user_dict["hashed_password"] = get_password_hash(
            user_dict.pop("password")
        )

        user_dict.update({
            "role": "user", 
            "is_active": True,
            "is_verified": False,  # Mặc định chưa xác thực
            "followers_count": 0,
            "following_count": 0,
            "posts_count": 0,
            "shop_id": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        existing_user = await self.collection.find_one({
            "$or": [
                {"email": user_in.email},
                {"username": user_in.username}
            ]
        })
        if existing_user:
            return None

        result = await self.collection.insert_one(user_dict)
        user_id = str(result.inserted_id)
        
        # Tạo verification token và gửi email xác thực
        verification_token = await self.token_service.create_verification_token(user_id)
        
        # Tạo URL xác thực
        verification_url = f"{settings.BACKEND_URL}/api/v1/auth/verify-email?token={verification_token}"
        
        # Gửi email xác thực (fire-and-forget, không block response)
        import asyncio
        asyncio.create_task(
            self.email_service.send_verification_email(
                to_email=user_in.email,
                username=user_in.username,
                verification_url=verification_url
            )
        )
        
        # Thông báo cho admin
        admin_users = await self.collection.find({"role": "admin"}).to_list(length=None)
        
        for admin in admin_users:
            await self.admin_notification_service.create_notification(
                user_id=str(admin["_id"]),
                type="new_user",
                title="Người dùng mới đăng ký",
                message=f"Người dùng {user_in.username} vừa đăng ký tài khoản mới",
                reference_id=user_id
            )

        return user_id

    async def get_all_users(self):
        users = []
        cursor = self.collection.find()
        async for document in cursor:
            document["_id"] = str(document["_id"])
            # Xóa mật khẩu
            document.pop("hashed_password", None)
            users.append(document)
        return users

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        try:
            user = await self.collection.find_one({"_id": ObjectId(user_id)})
            if user:
                user["id"] = str(user["_id"])
                user["_id"] = str(user["_id"])
                # Giữ lại hashed_password cho các thao tác xác thực
                return user
            return None
        except Exception as e:
            print(f"Error getting user by id: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        user = await self.collection.find_one({"email": email})
        if user:
            user["id"] = str(user["_id"])
            user["_id"] = str(user["_id"])
            return user
        return None

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        user = await self.collection.find_one({"username": username})
        if user:
            user["id"] = str(user["_id"])
            user["_id"] = str(user["_id"])
            return user
        return None

    async def authenticate_user(self, username: str, password: str) -> Optional[dict]:
        user = await self.get_user_by_username(username)
        if not user:
            return None
        if not verify_password(password, user["hashed_password"]):
            return None
        return user
    
    async def update_user(self, user_id: str, user_update: UserUpdate):
        update_data = {k: v for k, v in user_update.model_dump().items() if v is not None}
        
        if "dob" in update_data and update_data["dob"]:
            update_data["dob"] = datetime.combine(update_data["dob"], datetime.min.time())
            
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        
        # Không cho phép cập nhật username (có thể thêm nếu muốn)
        update_data.pop("username", None)
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)}, {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete_user(self, user_id: str):
        result = await self.collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0

    async def update_last_login(self, user_id: str):
        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_login": datetime.utcnow()}}
        )

    async def verify_user_email(self, token: str) -> bool:
        """Xác thực email user qua token"""
        token_data = await self.token_service.verify_token(token)
        
        if not token_data:
            return False
        
        user_id = token_data["user_id"]
        
        # Cập nhật user thành đã xác thực
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_verified": True, "updated_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0
    
    async def resend_verification_email(self, email: str) -> bool:
        """Gửi lại email xác thực"""
        user = await self.get_user_by_email(email)
        
        if not user:
            return False
        
        if user.get("is_verified"):
            return False  # Đã xác thực rồi
        
        # Tạo token mới
        verification_token = await self.token_service.create_verification_token(user["id"])
        
        # Tạo URL xác thực
        verification_url = f"{settings.BACKEND_URL}/api/v1/auth/verify-email?token={verification_token}"
        
        # Gửi email
        await self.email_service.send_verification_email(
            to_email=email,
            username=user.get("username"),
            verification_url=verification_url
        )
        
        return True