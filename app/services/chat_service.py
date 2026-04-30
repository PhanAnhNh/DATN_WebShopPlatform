# app/services/chat_service.py
from typing import List, Dict, Optional
from bson import ObjectId
from datetime import datetime
from app.models.message_model import MessageCreate

class ChatService:
    def __init__(self, db):
        self.db = db
        self.message_collection = db["messages"]
        self.user_collection = db["users"]
        self.shop_collection = db["shops"]

    async def send_message(self, sender_id: str, receiver_id: str, content: str, sender_type: str = "user", message_type: str = "text") -> Dict:
        """Gửi tin nhắn - hỗ trợ user-user, user-shop, shop-user"""
        if sender_id == receiver_id:
            raise ValueError("Không thể nhắn tin cho chính mình")
        
        # Xác định loại người nhận
        from bson import ObjectId
        receiver_is_shop = await self.shop_collection.find_one({"_id": ObjectId(receiver_id)})
        receiver_type = "shop" if receiver_is_shop else "user"
        
        # Cho phép user nhắn cho shop và ngược lại (không cần kiểm tra bạn bè)
        # Chỉ user-user cần kiểm tra bạn bè
        if sender_type == "user" and receiver_type == "user":
            from app.services.friend_service import FriendService
            friend_service = FriendService(self.db)
            status = await friend_service.check_friendship(sender_id, receiver_id)
            if status.get("status") != "friends":
                raise ValueError("Chỉ có thể nhắn tin với bạn bè")
        
        # Lưu tin nhắn
        msg_dict = {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "sender_type": sender_type,
            "receiver_type": receiver_type,
            "content": content,
            "message_type": message_type,
            "is_read": False,
            "created_at": datetime.utcnow()
        }
        
        result = await self.message_collection.insert_one(msg_dict)
        msg_dict["_id"] = str(result.inserted_id)
        
        return msg_dict

    async def _get_receiver_type(self, receiver_id: str) -> str:
        """Xác định loại người nhận (user hoặc shop)"""
        # Kiểm tra xem có phải shop không
        shop = await self.shop_collection.find_one({"_id": ObjectId(receiver_id)})
        if shop:
            return "shop"
        
        # Kiểm tra xem có phải user không
        user = await self.user_collection.find_one({"_id": ObjectId(receiver_id)})
        if user:
            return "user"
        
        raise ValueError(f"Không tìm thấy người nhận với ID: {receiver_id}")

    async def _can_send_message(self, sender_id: str, receiver_id: str, sender_type: str, receiver_type: str) -> bool:
        """Kiểm tra xem có được phép nhắn tin không"""
        # User có thể nhắn cho shop (không cần là bạn bè)
        if sender_type == "user" and receiver_type == "shop":
            # Kiểm tra shop có tồn tại và hoạt động không
            shop = await self.shop_collection.find_one({"_id": ObjectId(receiver_id), "is_active": True})
            return shop is not None
        
        # Shop có thể nhắn cho user (không cần là bạn bè)
        if sender_type == "shop" and receiver_type == "user":
            # Kiểm tra user có tồn tại và hoạt động không
            user = await self.user_collection.find_one({"_id": ObjectId(receiver_id), "is_active": True})
            return user is not None
        
        # User - User: cần là bạn bè
        if sender_type == "user" and receiver_type == "user":
            from app.services.friend_service import FriendService
            friend_service = FriendService(self.db)
            status = await friend_service.check_friendship(sender_id, receiver_id)
            return status.get("status") == "friends"
        
        # Shop - Shop: không cho phép (có thể bỏ qua hoặc xử lý sau)
        return False

    async def get_conversation(self, user1_id: str, user2_id: str, limit: int = 50, skip: int = 0, user1_type: str = "user", user2_type: str = "user") -> List[Dict]:
        """Lấy tin nhắn giữa 2 người dùng (có thể là user hoặc shop)"""
        cursor = self.message_collection.find({
            "$or": [
                {"sender_id": user1_id, "receiver_id": user2_id},
                {"sender_id": user2_id, "receiver_id": user1_id}
            ]
        }).sort("created_at", -1).skip(skip).limit(limit)

        messages = []
        async for msg in cursor:
            # Lấy thông tin người gửi
            sender_info = await self._get_sender_info(msg["sender_id"], msg.get("sender_type", "user"))
            msg["id"] = str(msg["_id"])
            msg.pop("_id")
            msg["sender_name"] = sender_info.get("name", "Unknown")
            msg["sender_avatar"] = sender_info.get("avatar")
            messages.append(msg)

        return list(reversed(messages))

    async def _get_sender_info(self, sender_id: str, sender_type: str) -> Dict:
        """Lấy thông tin người gửi (user hoặc shop)"""
        if sender_type == "shop":
            shop = await self.shop_collection.find_one({"_id": ObjectId(sender_id)})
            if shop:
                return {
                    "name": shop.get("name", "Cửa hàng"),
                    "avatar": shop.get("logo_url")
                }
        else:
            user = await self.user_collection.find_one({"_id": ObjectId(sender_id)})
            if user:
                return {
                    "name": user.get("full_name") or user.get("username", "Người dùng"),
                    "avatar": user.get("avatar_url")
                }
        
        return {"name": "Unknown", "avatar": None}

    async def get_recent_chats(self, user_id: str, user_type: str = "user") -> List[Dict]:
        """Lấy danh sách chat gần đây cho user hoặc shop"""
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
            {"$limit": 50}
        ]

        cursor = self.message_collection.aggregate(pipeline)
        chats = []
        async for chat in cursor:
            other_user_id = str(chat["_id"])
            other_info = await self._get_sender_info(other_user_id, chat["last_message"].get("receiver_type") if chat["last_message"]["receiver_id"] == user_id else chat["last_message"].get("sender_type"))
            
            chats.append({
                "user_id": other_user_id,
                "full_name": other_info.get("name", "Unknown"),
                "avatar_url": other_info.get("avatar"),
                "last_message": chat["last_message"]["content"][:60] + "..." if len(chat["last_message"]["content"]) > 60 else chat["last_message"]["content"],
                "last_message_time": chat["last_message"]["created_at"],
                "unread_count": chat["unread_count"],
                "type": chat["last_message"].get("receiver_type") if chat["last_message"]["receiver_id"] == user_id else chat["last_message"].get("sender_type")
            })
        return chats

    async def get_shop_conversations(self, shop_id: str) -> List[Dict]:
        """Lấy danh sách user đã chat với shop"""
        pipeline = [
            {"$match": {"$or": [{"sender_id": shop_id}, {"receiver_id": shop_id}]}},
            {"$sort": {"created_at": -1}},
            {
                "$group": {
                    "_id": {
                        "$cond": [
                            {"$eq": ["$sender_id", shop_id]},
                            "$receiver_id",
                            "$sender_id"
                        ]
                    },
                    "last_message": {"$first": "$$ROOT"},
                    "unread_count": {
                        "$sum": {"$cond": [{"$and": [{"$eq": ["$receiver_id", shop_id]}, {"$eq": ["$is_read", False]}]}, 1, 0]}
                    }
                }
            }
        ]

        cursor = self.message_collection.aggregate(pipeline)
        conversations = []
        async for conv in cursor:
            user_id = str(conv["_id"])
            user = await self.user_collection.find_one({"_id": ObjectId(user_id)})
            if user:
                conversations.append({
                    "user_id": user_id,
                    "full_name": user.get("full_name") or user.get("username", "Người dùng"),
                    "avatar_url": user.get("avatar_url"),
                    "last_message": conv["last_message"]["content"][:60] + "..." if len(conv["last_message"]["content"]) > 60 else conv["last_message"]["content"],
                    "last_message_time": conv["last_message"]["created_at"],
                    "unread_count": conv["unread_count"]
                })
        return conversations

    async def mark_messages_as_read(self, user_id: str, sender_id: str):
        """Đánh dấu tin nhắn từ sender_id là đã đọc"""
        await self.message_collection.update_many(
            {
                "sender_id": sender_id,
                "receiver_id": user_id,
                "is_read": False
            },
            {"$set": {"is_read": True}}
        )

    async def get_unread_count(self, user_id: str) -> int:
        """Lấy tổng số tin nhắn chưa đọc của user/shop"""
        count = await self.message_collection.count_documents({
            "receiver_id": user_id,
            "is_read": False
        })
        return count