# app/services/post_comments_services.py
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
        data["updated_at"] = None  # Khởi tạo updated_at

        # Xóa parent_id nếu không có
        if "parent_id" in data and not data["parent_id"]:
            del data["parent_id"]

        result = await self.collection.insert_one(data)

        await self.db["social_posts"].update_one(
            {"_id": ObjectId(data["post_id"])},
            {"$inc": {"stats.comment_count": 1}}
        )

        # Trả về comment vừa tạo với đầy đủ thông tin user
        comment = await self.collection.find_one({"_id": result.inserted_id})
        if comment:
            comment["_id"] = str(comment["_id"])
            comment["post_id"] = str(comment["post_id"])
            comment["user_id"] = str(comment["user_id"])
            
            # Lấy thông tin user
            user = await self.db["users"].find_one({"_id": ObjectId(user_id)})
            if user:
                comment["author_id"] = str(user["_id"])
                comment["author_name"] = user.get("full_name") or user.get("username", "Người dùng")
                comment["author_avatar"] = user.get("avatar_url")
            
            return comment
        
        return str(result.inserted_id)

    async def get_comments_by_post(self, post_id: str):
        """Lấy tất cả bình luận của bài viết với thông tin người dùng"""
        pipeline = [
            {"$match": {"post_id": ObjectId(post_id)}},
            {"$sort": {"created_at": 1}},  # Sắp xếp theo thời gian tăng dần (cũ lên trước)
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
            # Chuyển đổi ObjectId sang string
            doc["_id"] = str(doc["_id"])
            doc["post_id"] = str(doc["post_id"])
            doc["user_id"] = str(doc["user_id"])
            
            # Thêm các trường author cho frontend
            doc["author_id"] = doc["user_id"]
            doc["author_name"] = doc["user_info"].get("full_name") or doc["user_info"].get("username", "Người dùng")
            doc["author_avatar"] = doc["user_info"].get("avatar_url")
            
            # Thêm trường content (từ model PostCommentBase)
            if "content" not in doc:
                doc["content"] = doc.get("content", "")
            
            # Xóa user_info khỏi response
            if "user_info" in doc:
                del doc["user_info"]
            
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

        if result:
            result["_id"] = str(result["_id"])
            result["post_id"] = str(result["post_id"])
            result["user_id"] = str(result["user_id"])
            
            # Lấy thông tin user
            user = await self.db["users"].find_one({"_id": ObjectId(user_id)})
            if user:
                result["author_id"] = str(user["_id"])
                result["author_name"] = user.get("full_name") or user.get("username", "Người dùng")
                result["author_avatar"] = user.get("avatar_url")

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