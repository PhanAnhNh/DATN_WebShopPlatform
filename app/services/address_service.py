# app/services/address_service.py
from bson import ObjectId
from datetime import datetime
from typing import List, Optional


class AddressService:
    def __init__(self, db):
        self.collection = db["addresses"]

    async def create_address(self, user_id: str, data: dict) -> dict:
        """Tạo địa chỉ mới"""
        data["user_id"] = ObjectId(user_id)
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()
        
        # Nếu địa chỉ này là mặc định, cập nhật các địa chỉ khác không còn mặc định
        if data.get("is_default"):
            await self.collection.update_many(
                {"user_id": ObjectId(user_id)},
                {"$set": {"is_default": False}}
            )
        
        result = await self.collection.insert_one(data)
        
        address = await self.collection.find_one({"_id": result.inserted_id})
        if address:
            address["_id"] = str(address["_id"])
            address["user_id"] = str(address["user_id"])
        
        return address

    async def get_user_addresses(self, user_id: str) -> List[dict]:
        """Lấy tất cả địa chỉ của người dùng"""
        addresses = []
        cursor = self.collection.find({"user_id": ObjectId(user_id)}).sort("is_default", -1)
        
        async for addr in cursor:
            addr["_id"] = str(addr["_id"])
            addr["user_id"] = str(addr["user_id"])
            addresses.append(addr)
        
        return addresses

    async def get_address_by_id(self, address_id: str, user_id: str) -> Optional[dict]:
        """Lấy địa chỉ theo ID (kiểm tra quyền sở hữu)"""
        address = await self.collection.find_one({
            "_id": ObjectId(address_id),
            "user_id": ObjectId(user_id)
        })
        
        if address:
            address["_id"] = str(address["_id"])
            address["user_id"] = str(address["user_id"])
        
        return address

    async def update_address(self, address_id: str, user_id: str, data: dict) -> Optional[dict]:
        """Cập nhật địa chỉ"""
        # Nếu cập nhật thành địa chỉ mặc định
        if data.get("is_default"):
            await self.collection.update_many(
                {"user_id": ObjectId(user_id)},
                {"$set": {"is_default": False}}
            )
        
        data["updated_at"] = datetime.utcnow()
        
        await self.collection.update_one(
            {"_id": ObjectId(address_id), "user_id": ObjectId(user_id)},
            {"$set": data}
        )
        
        return await self.get_address_by_id(address_id, user_id)

    async def delete_address(self, address_id: str, user_id: str) -> bool:
        """Xóa địa chỉ"""
        result = await self.collection.delete_one({
            "_id": ObjectId(address_id),
            "user_id": ObjectId(user_id)
        })
        return result.deleted_count > 0

    async def set_default_address(self, address_id: str, user_id: str) -> Optional[dict]:
        """Đặt địa chỉ mặc định"""
        # Đặt tất cả địa chỉ khác không mặc định
        await self.collection.update_many(
            {"user_id": ObjectId(user_id)},
            {"$set": {"is_default": False}}
        )
        
        # Đặt địa chỉ này thành mặc định
        await self.collection.update_one(
            {"_id": ObjectId(address_id), "user_id": ObjectId(user_id)},
            {"$set": {"is_default": True, "updated_at": datetime.utcnow()}}
        )
        
        return await self.get_address_by_id(address_id, user_id)

    async def get_default_address(self, user_id: str) -> Optional[dict]:
        """Lấy địa chỉ mặc định của người dùng"""
        address = await self.collection.find_one({
            "user_id": ObjectId(user_id),
            "is_default": True
        })
        
        if address:
            address["_id"] = str(address["_id"])
            address["user_id"] = str(address["user_id"])
        
        return address