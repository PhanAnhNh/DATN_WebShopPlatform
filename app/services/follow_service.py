# app/services/follow_service.py
from bson import ObjectId
from datetime import datetime
from typing import List, Dict

class FollowService:

    def __init__(self, db):
        self.collection = db["follows"]
        self.user_collection = db["users"]

    async def toggle_follow(self, follower_id: str, following_id: str):
        """Toggle follow/unfollow"""
        # Không cho phép tự follow chính mình
        if follower_id == following_id:
            return {"following": False, "error": "Cannot follow yourself"}
            
        existing = await self.collection.find_one({
            "follower_id": ObjectId(follower_id),
            "following_id": ObjectId(following_id)
        })

        if existing:
            # Unfollow
            await self.collection.delete_one({"_id": existing["_id"]})
            return {"following": False, "message": "Unfollowed successfully"}
        else:
            # Follow
            await self.collection.insert_one({
                "follower_id": ObjectId(follower_id),
                "following_id": ObjectId(following_id),
                "created_at": datetime.utcnow()
            })
            return {"following": True, "message": "Followed successfully"}
    
    async def count_followers(self, user_id: str) -> int:
        """Đếm số người theo dõi user"""
        return await self.collection.count_documents({
            "following_id": ObjectId(user_id)
        })
    
    async def count_following(self, user_id: str) -> int:
        """Đếm số người user đang theo dõi"""
        return await self.collection.count_documents({
            "follower_id": ObjectId(user_id)
        })
    
    async def is_following(self, follower_id: str, following_id: str) -> bool:
        """Kiểm tra xem follower_id có đang follow following_id không"""
        if follower_id == following_id:
            return False
            
        existing = await self.collection.find_one({
            "follower_id": ObjectId(follower_id),
            "following_id": ObjectId(following_id)
        })
        return existing is not None
    
    async def get_followers(self, user_id: str, limit: int = 20, skip: int = 0) -> List[Dict]:
        """Lấy danh sách những người đang theo dõi user"""
        pipeline = [
            {"$match": {"following_id": ObjectId(user_id)}},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "follower_id",
                    "foreignField": "_id",
                    "as": "user_info"
                }
            },
            {"$unwind": "$user_info"},
            {
                "$project": {
                    "_id": {"$toString": "$user_info._id"},
                    "full_name": "$user_info.full_name",
                    "username": "$user_info.username",
                    "avatar_url": "$user_info.avatar_url",
                    "followed_at": "$created_at"
                }
            }
        ]
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)

    async def get_following(self, user_id: str, limit: int = 20, skip: int = 0) -> List[Dict]:
        """Lấy danh sách những người user đang theo dõi"""
        pipeline = [
            {"$match": {"follower_id": ObjectId(user_id)}},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "following_id",
                    "foreignField": "_id",
                    "as": "user_info"
                }
            },
            {"$unwind": "$user_info"},
            {
                "$project": {
                    "_id": {"$toString": "$user_info._id"},
                    "full_name": "$user_info.full_name",
                    "username": "$user_info.username",
                    "avatar_url": "$user_info.avatar_url",
                    "followed_at": "$created_at"
                }
            }
        ]
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=limit)
    
    async def get_follow_stats(self, user_id: str) -> Dict:
        """Lấy thống kê follow"""
        followers_count = await self.count_followers(user_id)
        following_count = await self.count_following(user_id)
        return {
            "followers_count": followers_count,
            "following_count": following_count
        }