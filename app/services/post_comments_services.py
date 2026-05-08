# app/services/post_comments_services.py
from typing import Optional

from bson import ObjectId
from datetime import datetime

from app.services.ai_moderation_service import AIModerationService

class PostCommentService:
    def __init__(self, db):
        self.db = db
        self.collection = db["post_comments"]
        self.ai_moderation = AIModerationService(db)

    async def create_comment(self, user_id: str, data: dict):
        # AI MODERATION: Kiểm tra comment
        moderation_result = await self.ai_moderation.moderate_comment(data["content"])
        
        # Nếu comment bị đánh giá là spam hoặc toxic
        is_hidden = moderation_result["is_spam"] or moderation_result["is_toxic"]
        
        data["user_id"] = ObjectId(user_id)
        data["post_id"] = ObjectId(data["post_id"])
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = None
        data["is_hidden_by_ai"] = is_hidden  # Đánh dấu đã bị ẩn bởi AI
        data["ai_moderation"] = {
            "is_spam": moderation_result["is_spam"],
            "is_toxic": moderation_result["is_toxic"],
            "confidence": moderation_result["confidence"],
            "categories": moderation_result["categories"],
            "moderated_at": datetime.utcnow()
        }

        if "parent_id" in data and not data["parent_id"]:
            del data["parent_id"]

        result = await self.collection.insert_one(data)

        await self.db["social_posts"].update_one(
            {"_id": ObjectId(data["post_id"])},
            {"$inc": {"stats.comment_count": 1}}
        )

        comment = await self.collection.find_one({"_id": result.inserted_id})
        if comment:
            comment["_id"] = str(comment["_id"])
            comment["post_id"] = str(comment["post_id"])
            comment["user_id"] = str(comment["user_id"])
            
            user = await self.db["users"].find_one({"_id": ObjectId(user_id)})
            if user:
                comment["author_id"] = str(user["_id"])
                comment["author_name"] = user.get("full_name") or user.get("username", "Người dùng")
                comment["author_avatar"] = user.get("avatar_url")
            
            comment["is_hidden_by_ai"] = is_hidden
            
            return comment
        
        return str(result.inserted_id)

    async def get_comments_by_post(self, post_id: str, current_user_id: Optional[str] = None):
        """
        Lấy tất cả bình luận của bài viết
        """
        pipeline = [
            {"$match": {"post_id": ObjectId(post_id)}},
            {"$sort": {"created_at": 1}},
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
            doc["post_id"] = str(doc["post_id"])
            doc["user_id"] = str(doc["user_id"])
            doc["author_id"] = doc["user_id"]
            doc["author_name"] = doc["user_info"].get("full_name") or doc["user_info"].get("username", "Người dùng")
            doc["author_avatar"] = doc["user_info"].get("avatar_url")
            
            # ===== QUAN TRỌNG: Thêm trường is_hidden_by_ai vào response =====
            # Lấy giá trị từ database, mặc định là False nếu không có
            doc["is_hidden_by_ai"] = doc.get("is_hidden_by_ai", False)
            
            # Thêm AI moderation nếu có
            if "ai_moderation" in doc:
                doc["ai_moderation"] = doc["ai_moderation"]
            
            # Xóa user_info
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

    async def unhide_comment(self, comment_id: str, current_user_id: str):
        """Bỏ ẩn comment (chỉ chủ bài viết hoặc admin)"""
        comment = await self.collection.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            return False
        
        # Lấy bài viết để kiểm tra quyền
        post = await self.db["social_posts"].find_one({"_id": comment["post_id"]})
        if not post:
            return False
        
        is_post_owner = str(post["author_id"]) == current_user_id
        
        # Kiểm tra admin
        user = await self.db["users"].find_one({"_id": ObjectId(current_user_id)})
        is_admin = user and user.get("role") == "admin"
        
        if not is_post_owner and not is_admin:
            return False
        
        result = await self.collection.update_one(
            {"_id": ObjectId(comment_id)},
            {"$set": {"is_hidden_by_ai": False}}
        )
        
        return result.modified_count > 0