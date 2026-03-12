from unittest import result

from bson import ObjectId
from datetime import datetime

class PostCommentService:
    def __init__(self, db):
        self.db = db
        self.collection = db["post_comments"]

    async def create_comment(self, user_id: str, data: dict):

        data["user_id"] = ObjectId(user_id)
        data["post_id"] = ObjectId(data["post_id"])
        data["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(data)

        await self.db["social_posts"].update_one(
            {"_id": ObjectId(data["post_id"])},
            {"$inc": {"stats.comment_count": 1}}
        )

        return str(result.inserted_id)

    async def get_comments_by_post(self, post_id: str):
        # Dùng Aggregate để lấy kèm thông tin User (Tên, Avatar)
        pipeline = [
            {"$match": {"post_id": ObjectId(post_id)}},
            {"$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user_info"
            }},
            {"$unwind": "$user_info"}
        ]
        cursor = self.collection.aggregate(pipeline)
        comments = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["author_name"] = doc["user_info"].get("full_name")
            doc["author_avatar"] = doc["user_info"].get("avatar_url")
            comments.append(doc)
        return comments
    

    async def update_comment(self, comment_id: str, user_id: str, update_data):

        update_dict = {
            k: v for k, v in update_data.dict().items()
            if v is not None
        }

        if not update_dict:
            return None

        update_dict["updated_at"] = datetime.utcnow()

        result = await self.collection.find_one_and_update(
            {
                "_id": ObjectId(comment_id),
                "user_id": ObjectId(user_id)
            },
            {"$set": update_dict},
            return_document=True
        )

        return result
    
    async def delete_comment(self, comment_id: str, user_id: str):

        comment = await self.collection.find_one({
            "_id": ObjectId(comment_id)
        })

        if not comment:
            return False

        result = await self.collection.delete_one({
            "_id": ObjectId(comment_id),
            "user_id": ObjectId(user_id)
        })

        if result.deleted_count == 1:

            await self.db["social_posts"].update_one(
                {"_id": comment["post_id"]},
                {"$inc": {"stats.comment_count": -1}}
            )

            return True

        return False