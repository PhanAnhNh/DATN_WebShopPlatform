from bson import ObjectId
from datetime import datetime

class PostLikeService:
    def __init__(self, db):
        self.collection = db["post_likes"]
        self.post_collection = db["social_posts"]

    async def toggle_like(self, post_id: str, user_id: str):

        existing = await self.collection.find_one({
            "post_id": ObjectId(post_id),
            "user_id": ObjectId(user_id)
        })

        if existing:
            await self.collection.delete_one({"_id": existing["_id"]})

            await self.post_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$inc": {"stats.like_count": -1}}
            )

            return {"liked": False}

        await self.collection.insert_one({
            "post_id": ObjectId(post_id),
            "user_id": ObjectId(user_id),
            "created_at": datetime.utcnow()
        })

        await self.post_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"stats.like_count": 1}}
        )

        return {"liked": True}
    
    async def get_likes_by_post(self, post_id: str):

        cursor = self.collection.aggregate([
            {"$match": {"post_id": ObjectId(post_id)}},

            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user"
                }
            },

            {"$unwind": "$user"}
        ])

        results = []
        async for doc in cursor:
            results.append({
                "user_id": str(doc["user_id"]),
                "name": doc["user"]["full_name"],
                "avatar": doc["user"]["avatar_url"]
            })

        return results
    
    async def is_liked(self, post_id: str, user_id: str):

        like = await self.collection.find_one({
            "post_id": ObjectId(post_id),
            "user_id": ObjectId(user_id)
        })

        return like is not None