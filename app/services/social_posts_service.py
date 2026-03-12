from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from pymongo import ReturnDocument

from app.models.social_posts_model import SocialPostCreate, SocialPostUpdate


class SocialPostService:

    def __init__(self, db):
        self.collection = db["social_posts"]
        self.user_collection = db["users"]

    # =========================
    # CREATE POST
    # =========================
    async def create_post(self, post_data: SocialPostCreate, current_user) -> dict:

        new_post = post_data.dict()

        # Lấy author từ token
        new_post["author_id"] = ObjectId(current_user.id)
        new_post["author_type"] = current_user.role

        new_post["created_at"] = datetime.utcnow()

        new_post["stats"] = {
            "like_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "save_count": 0,
            "view_count": 0
        }

        new_post["is_active"] = True
        new_post["is_approved"] = True
        new_post["is_pinned"] = False
        new_post["report_count"] = 0
        new_post["feed_score"] = 0.0

        result = await self.collection.insert_one(new_post)

        new_post["_id"] = str(result.inserted_id)
        new_post["author_id"] = str(new_post["author_id"])

        return new_post

    # =========================
    # GET SOCIAL FEED
    # =========================
    async def get_feed(
        self,
        limit: int = 10,
        skip: int = 0,
        category: Optional[str] = None
    ) -> List[dict]:

        match_query = {"is_active": True}

        if category and category != "general":
            match_query["product_category"] = category

        pipeline = [
            {"$match": match_query},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "author_id",
                    "foreignField": "_id",
                    "as": "author_info"
                }
            },
            {
                "$unwind": {
                    "path": "$author_info",
                    "preserveNullAndEmptyArrays": True
                }
            }
        ]

        cursor = self.collection.aggregate(pipeline)

        posts = []

        async for doc in cursor:

            doc["_id"] = str(doc["_id"])
            doc["author_id"] = str(doc["author_id"])

            author = doc.get("author_info", {})

            doc["author_name"] = author.get("full_name", "Người dùng hệ thống")
            doc["author_avatar"] = author.get("avatar_url")

            posts.append(doc)

        return posts

    # =========================
    # UPDATE POST
    # =========================
    async def update_post(
        self,
        post_id: str,
        user_id: str,
        update_data: SocialPostUpdate
    ) -> Optional[dict]:

        query = {
            "_id": ObjectId(post_id),
            "author_id": ObjectId(user_id)
        }

        update_dict = {
            k: v
            for k, v in update_data.dict().items()
            if v is not None
        }

        update_dict["updated_at"] = datetime.utcnow()

        updated_post = await self.collection.find_one_and_update(
            query,
            {"$set": update_dict},
            return_document=ReturnDocument.AFTER
        )

        if updated_post:
            updated_post["_id"] = str(updated_post["_id"])
            updated_post["author_id"] = str(updated_post["author_id"])

        return updated_post

    # =========================
    # GET POSTS BY USER
    # =========================
    async def get_user_posts(
        self,
        user_id: str,
        limit: int = 10,
        skip: int = 0
    ) -> List[dict]:

        match_query = {
            "author_id": ObjectId(user_id)
        }

        pipeline = [
            {"$match": match_query},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "author_id",
                    "foreignField": "_id",
                    "as": "author_info"
                }
            },
            {
                "$unwind": {
                    "path": "$author_info",
                    "preserveNullAndEmptyArrays": True
                }
            }
        ]

        cursor = self.collection.aggregate(pipeline)

        posts = []

        async for doc in cursor:

            doc["_id"] = str(doc["_id"])
            doc["author_id"] = str(doc["author_id"])

            author = doc.get("author_info", {})

            doc["author_name"] = author.get("full_name", "Người dùng hệ thống")
            doc["author_avatar"] = author.get("avatar_url")

            posts.append(doc)

        return posts
    
    async def delete_post(self, post_id: str, user_id: str) -> bool:

        result = await self.collection.update_one(
            {
                "_id": ObjectId(post_id),
                "author_id": ObjectId(user_id)
            },
            {
                "$set": {
                    "is_active": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return result.modified_count > 0