from datetime import datetime
from bson import ObjectId
from typing import Optional
import math
import logging

logger = logging.getLogger(__name__)

class NotificationService:

    def __init__(self, db):
        self.collection = db["notifications"]

    async def create_notification(
        self, 
        user_id: str, 
        type: str, 
        title: str, 
        message: str, 
        reference_id: Optional[str] = None,
        image_url: Optional[str] = None,
        extra_data: Optional[dict] = None,
        socket_manager = None  # Thêm socket_manager
    ) -> str:
        """Tạo thông báo mới và gửi real-time qua socket"""
        notification = {
            "user_id": user_id,
            "type": type,
            "title": title,
            "message": message,
            "reference_id": reference_id,
            "image_url": image_url,
            "is_read": False,
            "created_at": datetime.utcnow(),
            "extra_data": extra_data or {}
        }
        
        result = await self.collection.insert_one(notification)
        notification_id = str(result.inserted_id)
        
        # Gửi real-time notification qua socket
        if socket_manager:
            await socket_manager.send_notification(
                user_id=user_id,
                notification={
                    "id": notification_id,
                    "type": type,
                    "title": title,
                    "message": message,
                    "image_url": image_url,
                    "extra_data": extra_data,
                    "created_at": notification["created_at"].isoformat()
                }
            )
        
        return notification_id

    async def get_notifications(
        self, 
        user_id: str, 
        page: int = 1, 
        limit: int = 20,
        unread_only: bool = False
    ):
        """Lấy danh sách thông báo có phân trang"""
        try:
            # 🔥 Quan trọng: Chuyển đổi user_id sang ObjectId
            user_object_id = ObjectId(user_id)
            
            query = {"user_id": user_object_id}
            
            if unread_only:
                query["is_read"] = False
            
            # Đếm tổng số
            total = await self.collection.count_documents(query)
            
            # Lấy danh sách
            skip = (page - 1) * limit
            cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            
            notifications = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                doc["user_id"] = str(doc["user_id"])
                notifications.append(doc)
            
            return {
                "data": notifications,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_pages": math.ceil(total / limit) if total > 0 else 1
                }
            }
        except Exception as e:
            logger.error(f"Error getting notifications: {e}")
            return {
                "data": [],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": 0,
                    "total_pages": 1
                }
            }

    async def get_unread_count(self, user_id: str):
        """Lấy số lượng thông báo chưa đọc"""
        try:
            user_object_id = ObjectId(user_id)
            count = await self.collection.count_documents({
                "user_id": user_object_id,
                "is_read": False
            })
            logger.info(f"Unread count for user {user_id}: {count}")
            return count
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0

    async def mark_as_read(self, notification_id: str, user_id: str):
        """Đánh dấu thông báo đã đọc"""
        try:
            result = await self.collection.update_one(
                {
                    "_id": ObjectId(notification_id),
                    "user_id": ObjectId(user_id)
                },
                {"$set": {"is_read": True}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error marking as read: {e}")
            return False

    async def mark_all_as_read(self, user_id: str):
        """Đánh dấu tất cả thông báo đã đọc"""
        try:
            result = await self.collection.update_many(
                {
                    "user_id": ObjectId(user_id),
                    "is_read": False
                },
                {"$set": {"is_read": True}}
            )
            return result.modified_count
        except Exception as e:
            logger.error(f"Error marking all as read: {e}")
            return 0

    async def delete_notification(self, notification_id: str, user_id: str):
        """Xóa thông báo"""
        try:
            result = await self.collection.delete_one({
                "_id": ObjectId(notification_id),
                "user_id": ObjectId(user_id)
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting notification: {e}")
            return False

    async def delete_all_notifications(self, user_id: str):
        """Xóa tất cả thông báo của user"""
        try:
            result = await self.collection.delete_many({
                "user_id": ObjectId(user_id)
            })
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting all notifications: {e}")
            return 0