from typing import List, Dict
from bson import ObjectId
from datetime import datetime
from app.models.message_model import MessageCreate
from app.services.friend_service import FriendService

class ChatService:
    def __init__(self, db):
        self.db = db
        self.message_collection = db["messages"]
        self.user_collection = db["users"]

    async def send_message(self, sender_id: str, message: MessageCreate) -> Dict:
        if sender_id == message.receiver_id:
            raise ValueError("Không thể nhắn tin cho chính mình")

        # Kiểm tra có phải bạn bè không
        friend_service = FriendService(self.db)
        status = await friend_service.check_friendship(sender_id, message.receiver_id)
        
        if status.get("status") != "friends":
            raise ValueError("Chỉ có thể nhắn tin với bạn bè")

        msg_dict = {
            "sender_id": sender_id,
            "receiver_id": message.receiver_id,
            "content": message.content,
            "message_type": message.message_type,
            "is_read": False,
            "created_at": datetime.utcnow()
        }

        result = await self.message_collection.insert_one(msg_dict)
        msg_dict["_id"] = str(result.inserted_id)

        return msg_dict

    async def get_conversation(self, user1_id: str, user2_id: str, limit: int = 50, skip: int = 0) -> List[Dict]:
        cursor = self.message_collection.find({
            "$or": [
                {"sender_id": user1_id, "receiver_id": user2_id},
                {"sender_id": user2_id, "receiver_id": user1_id}
            ]
        }).sort("created_at", -1).skip(skip).limit(limit)

        messages = []
        async for msg in cursor:
            # Lấy thông tin người gửi
            sender = await self.user_collection.find_one({"_id": ObjectId(msg["sender_id"])})
            msg["id"] = str(msg["_id"])
            msg.pop("_id")
            msg["sender_name"] = sender.get("full_name") or sender.get("username") if sender else "Unknown"
            msg["sender_avatar"] = sender.get("avatar_url") if sender else None
            messages.append(msg)

        return list(reversed(messages))  # sắp xếp cũ → mới

    async def get_recent_chats(self, user_id: str, limit: int = 20):
        """Lấy danh sách chat gần đây (người chat cuối cùng)"""
        pipeline = [
            {"$match": {"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]}},
            {"$sort": {"created_at": -1}},
            {
                "$group": {
                    "_id": {
                        "$cond": [
                            {"$eq": ["$sender_id", user_id]},
                            "$receiver_id",
                            "$sender_id"
                        ]
                    },
                    "last_message": {"$first": "$$ROOT"},
                    "unread_count": {
                        "$sum": {"$cond": [{"$and": [{"$eq": ["$receiver_id", user_id]}, {"$eq": ["$is_read", False]}]}, 1, 0]}
                    }
                }
            },
            {"$limit": limit}
        ]

        cursor = self.message_collection.aggregate(pipeline)
        chats = []
        async for chat in cursor:
            other_user_id = str(chat["_id"])
            user = await self.user_collection.find_one({"_id": ObjectId(other_user_id)})
            
            chats.append({
                "user_id": other_user_id,
                "full_name": user.get("full_name") or user.get("username") if user else "Unknown",
                "avatar_url": user.get("avatar_url") if user else None,
                "last_message": chat["last_message"]["content"][:60] + "..." if len(chat["last_message"]["content"]) > 60 else chat["last_message"]["content"],
                "last_message_time": chat["last_message"]["created_at"],
                "unread_count": chat["unread_count"]
            })
        return chats

    async def mark_as_read(self, user_id: str, sender_id: str):
        await self.message_collection.update_many(
            {"sender_id": sender_id, "receiver_id": user_id, "is_read": False},
            {"$set": {"is_read": True}}
        )

    async def get_unread_count(self, user_id: str) -> int:
        """Lấy tổng số tin nhắn chưa đọc của user"""
        count = await self.message_collection.count_documents({
            "receiver_id": user_id,
            "is_read": False
        })
        return count    

    async def mark_messages_as_read(self, user_id: str, sender_id: str):
        """Đánh dấu tất cả tin nhắn từ sender_id là đã đọc"""
        await self.message_collection.update_many(
            {
                "sender_id": sender_id,
                "receiver_id": user_id,
                "is_read": False
            },
            {"$set": {"is_read": True}}
        )
