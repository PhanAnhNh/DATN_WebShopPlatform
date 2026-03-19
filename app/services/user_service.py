# app/services/user_service.py
from app.db.mongodb import get_database
from app.core.security import get_password_hash
from app.models.user_model import UserCreate, UserUpdate
from bson import ObjectId
from datetime import datetime

class UserService:
    def __init__(self, db=None):
        # Sửa cách kiểm tra db
        if db is not None:  # Thay vì if db:
            self.db = db
            self.collection = db.users
        else:
            self.db = get_database()
            self.collection = self.db.users

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
            "is_verified": False,
            "followers_count": 0,
            "following_count": 0,
            "posts_count": 0,
            "shop_id": None,
            "created_at": datetime.utcnow(),
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
        return str(result.inserted_id)

    async def get_all_users(self):
        users = []
        cursor = self.collection.find()
        async for document in cursor:
            document["_id"] = str(document["_id"])
            users.append(document)
        return users

    async def update_user(self, user_id: str, user_update: UserUpdate):
        update_data = {k: v for k, v in user_update.model_dump().items() if v is not None}
        
        if "dob" in update_data and update_data["dob"]:
            update_data["dob"] = datetime.combine(update_data["dob"], datetime.min.time())
            
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
            
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)}, {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete_user(self, user_id: str):
        result = await self.collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0

    async def get_user_by_username(self, username: str):
        user = await self.collection.find_one({"username": username})
        if user:
            user["_id"] = str(user["_id"])
            return user
        return None

    async def get_user_by_id(self, user_id: str):
        try:
            user = await self.collection.find_one({"_id": ObjectId(user_id)})
            if user:
                user["_id"] = str(user["_id"])
                return user
            return None
        except Exception:
            return None