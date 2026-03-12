from bson import ObjectId
from datetime import datetime

class PostShareService:

    def __init__(self, db):
        self.collection = db["post_shares"]
        self.post_collection = db["social_posts"]

    async def share_post(self, post_id: str, user_id: str):

        # luôn tạo record share mới
        await self.collection.insert_one({
            "post_id": ObjectId(post_id),
            "user_id": ObjectId(user_id),
            "created_at": datetime.utcnow()
        })

        # tăng số lượt share
        await self.post_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"stats.share_count": 1}}
        )

        return {"shared": True}

    async def get_shares_by_post(self, post_id: str):

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