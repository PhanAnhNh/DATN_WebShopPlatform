# app/services/post_comments_services.py
from typing import Optional

from bson import ObjectId
from datetime import datetime

class PostCommentService:
    def __init__(self, db):
        self.db = db
        self.collection = db["post_comments"]

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

        # Xóa parent_id nếu không có
        if "parent_id" in data and not data["parent_id"]:
            del data["parent_id"]

        result = await self.collection.insert_one(data)

        # Vẫn tăng comment_count (comment bị ẩn vẫn tồn tại trong DB)
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
            
            # Thêm flag cho frontend biết comment đã bị ẩn
            comment["is_hidden_by_ai"] = is_hidden
            
            return comment
        
        return str(result.inserted_id)

    async def get_comments_by_post(self, post_id: str, current_user_id: Optional[str] = None):
        """
        Lấy tất cả bình luận của bài viết với thông tin người dùng
        Chỉ ẩn comment với người không phải chủ bài viết hoặc admin
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
        
        # Lấy thông tin bài viết để biết author
        post = await self.db["social_posts"].find_one({"_id": ObjectId(post_id)})
        is_post_owner = current_user_id and post and str(post["author_id"]) == current_user_id
        
        # Kiểm tra admin
        is_admin = False
        if current_user_id:
            user = await self.db["users"].find_one({"_id": ObjectId(current_user_id)})
            is_admin = user and user.get("role") == "admin"
        
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
            
            # Kiểm tra comment có bị ẩn không
            is_hidden = doc.get("is_hidden_by_ai", False)
            
            # Nếu comment bị ẩn và người dùng không phải chủ bài viết/admin
            if is_hidden and not is_post_owner and not is_admin:
                doc["content"] = "[Bình luận này bị ẩn do vi phạm tiêu chuẩn cộng đồng]"
                doc["is_hidden_by_ai"] = True
                doc["was_hidden"] = True
            else:
                doc["is_hidden_by_ai"] = False
                doc["was_hidden"] = is_hidden
            
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