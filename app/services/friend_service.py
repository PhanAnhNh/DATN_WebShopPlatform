from typing import List, Optional, Dict
from bson import ObjectId
from datetime import datetime
from app.models.friend_model import FriendRequestCreate, FriendRequestUpdate
from app.services.notification_service import NotificationService

class FriendService:
    def __init__(self, db):
        self.collection = db["friends"]
        self.user_collection = db["users"]
        self.notification_service = None  # Sẽ inject sau
        self.notification_service = NotificationService(db)
        
    # app/services/friend_service.py
    async def send_friend_request(self, user_id: str, friend_id: str) -> Dict:
        """Gửi lời mời kết bạn"""
        # Kiểm tra không tự kết bạn với chính mình
        if user_id == friend_id:
            raise ValueError("Không thể kết bạn với chính mình")
            
        # Kiểm tra user tồn tại và kiểm tra loại tài khoản
        friend = await self.user_collection.find_one({"_id": ObjectId(friend_id)})
        if not friend:
            raise ValueError("Người dùng không tồn tại")
        
        # THÊM: Kiểm tra nếu người nhận là shop thì không cho phép gửi lời mời
        if friend.get('user_type') == 'shop':
            raise ValueError("Không thể gửi lời mời kết bạn đến tài khoản shop")
        
        # Kiểm tra đã là bạn bè chưa
        existing_friendship = await self.collection.find_one({
            "$or": [
                {"user_id": user_id, "friend_id": friend_id},
                {"user_id": friend_id, "friend_id": user_id}
            ],
            "status": "accepted"
        })
        if existing_friendship:
            raise ValueError("Đã là bạn bè")
            
        # Kiểm tra đã có lời mời đang chờ chưa
        pending_request = await self.collection.find_one({
            "$or": [
                {"user_id": user_id, "friend_id": friend_id, "status": "pending"},
                {"user_id": friend_id, "friend_id": user_id, "status": "pending"}
            ]
        })
        if pending_request:
            if pending_request["user_id"] == user_id:
                raise ValueError("Đã gửi lời mời trước đó")
            else:
                raise ValueError("Người dùng đã gửi lời mời cho bạn")
        
        # Tạo lời mời mới
        friend_request = {
            "user_id": user_id,
            "friend_id": friend_id,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": None
        }
        
        result = await self.collection.insert_one(friend_request)
        friend_request["_id"] = str(result.inserted_id)
        
        # THÊM: Kiểm tra lại loại người nhận trước khi gửi thông báo
        # Chỉ gửi thông báo nếu người nhận không phải là shop
        if self.notification_service and friend.get('user_type') != 'shop':
            # Lấy thông tin người gửi
            sender = await self.user_collection.find_one({"_id": ObjectId(user_id)})
            sender_name = sender.get('full_name') or sender.get('username', 'Ai đó')
            
            # Tạo thông báo cho người nhận
            await self.notification_service.create_notification(
                user_id=friend_id,
                type="friend_request",
                title="Lời mời kết bạn",
                message=f"{sender_name} đã gửi lời mời kết bạn",
                reference_id=str(result.inserted_id),
                image_url=sender.get('avatar_url')
            )
        
        return friend_request
    
    async def accept_friend_request(self, request_id: str, user_id: str) -> bool:
        """Chấp nhận lời mời kết bạn"""
        result = await self.collection.update_one(
            {
                "_id": ObjectId(request_id),
                "friend_id": user_id,  # Người nhận mới có quyền chấp nhận
                "status": "pending"
            },
            {
                "$set": {
                    "status": "accepted",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            # Lấy thông tin để gửi thông báo
            request = await self.collection.find_one({"_id": ObjectId(request_id)})
            if request and self.notification_service:
                sender = await self.user_collection.find_one({"_id": ObjectId(request["user_id"])})
                await self.notification_service.create_notification(
                    user_id=request["user_id"],
                    type="friend_accepted",
                    title="Đã chấp nhận lời mời",
                    message=f"{sender.get('full_name', 'Ai đó')} đã chấp nhận lời mời kết bạn",
                    reference_id=str(request["_id"])
                )
            return True
        return False
    
    async def reject_friend_request(self, request_id: str, user_id: str) -> bool:
        """Từ chối lời mời kết bạn"""
        result = await self.collection.update_one(
            {
                "_id": ObjectId(request_id),
                "friend_id": user_id,
                "status": "pending"
            },
            {
                "$set": {
                    "status": "rejected",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    async def block_user(self, user_id: str, friend_id: str) -> bool:
        """Chặn người dùng"""
        # Xóa friendship hiện tại nếu có
        await self.collection.delete_many({
            "$or": [
                {"user_id": user_id, "friend_id": friend_id},
                {"user_id": friend_id, "friend_id": user_id}
            ]
        })
        
        # Tạo block record
        block = {
            "user_id": user_id,
            "friend_id": friend_id,
            "status": "blocked",
            "created_at": datetime.utcnow()
        }
        result = await self.collection.insert_one(block)
        return result.inserted_id is not None
    
    async def get_friends(self, user_id: str, limit: int = 20, skip: int = 0) -> List[Dict]:
        """Lấy danh sách bạn bè"""
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"user_id": user_id, "status": "accepted"},
                        {"friend_id": user_id, "status": "accepted"}
                    ]
                }
            },
            {"$skip": skip},
            {"$limit": limit},
            {
                "$project": {
                    "friend_id": {
                        "$cond": [
                            {"$eq": ["$user_id", user_id]},
                            "$friend_id",
                            "$user_id"
                        ]
                    }
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "friend_id",
                    "foreignField": "_id",
                    "as": "friend_info"
                }
            },
            {
                "$unwind": "$friend_info"
            },
            {
                "$project": {
                    "_id": 0,
                    "user_id": "$friend_id",
                    "full_name": "$friend_info.full_name",
                    "username": "$friend_info.username",
                    "avatar_url": "$friend_info.avatar_url",
                    "email": "$friend_info.email"
                }
            }
        ]
        
        cursor = self.collection.aggregate(pipeline)
        friends = []
        async for doc in cursor:
            doc["user_id"] = str(doc["user_id"])
            friends.append(doc)
        return friends
    
    async def get_pending_requests(self, user_id: str) -> List[Dict]:
        """Lấy danh sách lời mời kết bạn đang chờ"""
        pipeline = [
            {
                "$match": {
                    "friend_id": user_id,
                    "status": "pending"
                }
            },
            {"$sort": {"created_at": -1}},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "sender_info"
                }
            },
            {
                "$unwind": "$sender_info"
            },
            {
                "$project": {
                    "_id": {"$toString": "$_id"},
                    "user_id": {"$toString": "$user_id"},
                    "full_name": "$sender_info.full_name",
                    "username": "$sender_info.username",
                    "avatar_url": "$sender_info.avatar_url",
                    "created_at": 1
                }
            }
        ]
        
        cursor = self.collection.aggregate(pipeline)
        requests = []
        async for doc in cursor:
            requests.append(doc)
        return requests
    
    async def check_friendship(self, user_id: str, friend_id: str) -> Dict:
        """Kiểm tra trạng thái quan hệ giữa 2 người"""
        # Kiểm tra đã là bạn bè chưa
        is_friend = await self.collection.find_one({
            "$or": [
                {"user_id": user_id, "friend_id": friend_id},
                {"user_id": friend_id, "friend_id": user_id}
            ],
            "status": "accepted"
        })
        if is_friend:
            return {"status": "friends", "is_friend": True}
        
        # Kiểm tra lời mời đang chờ
        pending = await self.collection.find_one({
            "$or": [
                {"user_id": user_id, "friend_id": friend_id},
                {"user_id": friend_id, "friend_id": user_id}
            ],
            "status": "pending"
        })
        if pending:
            if pending["user_id"] == user_id:
                return {"status": "request_sent", "request_id": str(pending["_id"])}
            else:
                return {"status": "request_received", "request_id": str(pending["_id"])}
        
        # Kiểm tra bị chặn
        blocked = await self.collection.find_one({
            "$or": [
                {"user_id": user_id, "friend_id": friend_id, "status": "blocked"},
                {"user_id": friend_id, "friend_id": user_id, "status": "blocked"}
            ]
        })
        if blocked:
            if blocked["user_id"] == user_id:
                return {"status": "blocked_by_you"}
            else:
                return {"status": "blocked_by_them"}
        
        return {"status": "not_friends", "can_send_request": True}
    
    # app/services/friend_service.py
# Thêm method này vào class FriendService

    async def unfriend(self, user_id: str, friend_id: str) -> bool:
        """Hủy kết bạn"""
        # Xóa friendship record (cả 2 chiều)
        result = await self.collection.delete_many({
            "$or": [
                {"user_id": user_id, "friend_id": friend_id, "status": "accepted"},
                {"user_id": friend_id, "friend_id": user_id, "status": "accepted"}
            ]
        })
        
        if result.deleted_count > 0:
            # Có thể giảm số lượng bạn bè ở đây nếu cần
            # Hoặc tạo thông báo
            return True
        return False


    async def get_friend_count(self, user_id: str) -> int:
        """Lấy số lượng bạn bè"""
        count = await self.collection.count_documents({
            "$or": [
                {"user_id": user_id, "status": "accepted"},
                {"friend_id": user_id, "status": "accepted"}
            ]
        })
        return count