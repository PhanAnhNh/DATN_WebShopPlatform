from bson import ObjectId
from datetime import datetime
from typing import Dict, Optional
from app.models.admin_settings_model import AdminSettings

class AdminSettingsService:
    def __init__(self, db):
        self.db = db
        self.collection = db["admin_settings"]

    async def get_settings(self) -> Dict:
        """Lấy cài đặt hệ thống admin"""
        settings = await self.collection.find_one({})
        if not settings:
            # Tạo mặc định
            default = AdminSettings()
            result = await self.collection.insert_one(default.model_dump())
            settings = await self.collection.find_one({"_id": result.inserted_id})
        # Chuyển ObjectId sang string
        settings["_id"] = str(settings["_id"])
        return settings

    async def update_settings(self, data: dict) -> Dict:
        """Cập nhật cài đặt"""
        data["updated_at"] = datetime.utcnow()
        await self.collection.update_one({}, {"$set": data}, upsert=True)
        return await self.get_settings()