from bson import ObjectId
from datetime import datetime

class FollowService:

    def __init__(self, db):
        self.collection = db["follows"]

    async def toggle_follow(self, follower_id: str, following_id: str):

        existing = await self.collection.find_one({
            "follower_id": ObjectId(follower_id),
            "following_id": ObjectId(following_id)
        })

        if existing:
            await self.collection.delete_one({"_id": existing["_id"]})
            return {"following": False}

        await self.collection.insert_one({
            "follower_id": ObjectId(follower_id),
            "following_id": ObjectId(following_id),
            "created_at": datetime.utcnow()
        })

        return {"following": True}
    
    async def count_followers(self, user_id: str):
        return await self.collection.count_documents({
            "following_id": ObjectId(user_id)
        })
    
    async def count_following(self, user_id: str):
        return await self.collection.count_documents({
            "follower_id": ObjectId(user_id)
        })
    
    async def is_following(self, follower_id, following_id):

        existing = await self.collection.find_one({
            "follower_id": ObjectId(follower_id),
            "following_id": ObjectId(following_id)
        })

        return existing is not None
    
    async def get_followers(self, user_id: str):
        """Lấy danh sách những người đang theo dõi mình"""
        pipeline = [
            {"$match": {"following_id": ObjectId(user_id)}},
            {
                "$lookup": {
                    "from": "users",           # Tên collection chứa thông tin user
                    "localField": "follower_id",
                    "foreignField": "_id",
                    "as": "user_info"
                }
            },
            {"$unwind": "$user_info"},
            {
                "$project": {
                    "_id": 0,
                    "id": {"$toString": "$user_info._id"},
                    "name": "$user_info.name",
                    "avatar": "$user_info.avatar_url",
                    "followed_at": "$created_at"
                }
            }
        ]
        return await self.collection.aggregate(pipeline).to_list(length=100)

    async def get_following(self, user_id: str):
        """Lấy danh sách những người mình đang theo dõi"""
        pipeline = [
            {"$match": {"follower_id": ObjectId(user_id)}},
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
                    "_id": 0,
                    "id": {"$toString": "$user_info._id"},
                    "name": "$user_info.name",
                    "avatar": "$user_info.avatar_url",
                    "followed_at": "$created_at"
                }
            }
        ]
        return await self.collection.aggregate(pipeline).to_list(length=100)