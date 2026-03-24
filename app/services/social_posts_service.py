from datetime import datetime, timedelta
from typing import List, Optional
from bson import ObjectId
from pymongo import ReturnDocument

from app.models.social_posts_model import SocialPostCreate, SocialPostUpdate
from app.services.admin_notification_service import AdminNotificationService


class SocialPostService:

    def __init__(self, db):
        self.collection = db["social_posts"]
        self.user_collection = db["users"]
        self.db = db
        self.admin_notification_service = AdminNotificationService(db)

    async def create_post(self, post_data: SocialPostCreate, current_user) -> dict:
        new_post = post_data.dict()
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
        new_post["deleted_at"] = None
        new_post["is_permanently_deleted"] = False

        result = await self.collection.insert_one(new_post)
        post_id = str(result.inserted_id)

        await self.user_collection.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$inc": {"posts_count": 1}}
        )

        admin_users = await self.user_collection.find({"role": "admin"}).to_list(length=None)
        
        author_name = current_user.full_name or current_user.username
        
        for admin in admin_users:
            await self.admin_notification_service.create_notification(
                user_id=str(admin["_id"]),
                type="new_post",
                title="Bài viết mới được đăng",
                message=f"{author_name} vừa đăng bài viết mới: {post_data.content[:50] if post_data.content else '...'}",
                reference_id=post_id
            )
            
        new_post["_id"] = str(result.inserted_id)
        new_post["author_id"] = str(new_post["author_id"])
        return new_post

    async def get_user_posts(
        self,
        user_id: str,
        limit: int = 10,
        skip: int = 0,
        current_user_id: Optional[str] = None
    ) -> List[dict]:
        """
        Lấy bài viết của user theo user_id
        Có kiểm tra quyền truy cập dựa trên visibility
        """
        print(f"=== get_user_posts called with user_id: {user_id}, current_user_id: {current_user_id} ===")
        
        try:
            user_oid = ObjectId(user_id)
        except Exception as e:
            print(f"Invalid ObjectId: {user_id}")
            return []
            
        user = await self.user_collection.find_one({"_id": user_oid})
        print(f"User found: {user is not None}")
        
        if not user:
            return []
        
        # Xây dựng query cơ bản
        match_query = {
            "author_id": user_oid,
            "is_active": True,
            "is_permanently_deleted": False
        }
        
        # Kiểm tra quyền truy cập
        is_own_profile = current_user_id and str(current_user_id) == user_id
        
        if not is_own_profile and current_user_id:
            # Lấy danh sách bạn bè từ collection FRIENDS (không phải follows)
            friend_ids = []
            try:
                # Tìm các mối quan hệ bạn bè đã được chấp nhận
                # Kiểm tra cả 2 chiều: current_user là user_id hoặc friend_id
                friendships = await self.db["friends"].find({
                    "$or": [
                        {"user_id": current_user_id, "friend_id": user_id, "status": "accepted"},
                        {"user_id": user_id, "friend_id": current_user_id, "status": "accepted"}
                    ]
                }).to_list(length=None)
                
                # Nếu có friendship, họ là bạn bè
                is_friend = len(friendships) > 0
                print(f"Is friend: {is_friend}")
                
                # Nếu là bạn bè, cho phép xem bài viết "friends"
                if is_friend:
                    # Thêm current_user vào danh sách bạn bè để hiển thị bài viết "friends"
                    friend_ids = [ObjectId(current_user_id)]
            except Exception as e:
                print(f"Error getting friends: {e}")
            
            # Thêm điều kiện visibility
            if is_friend:
                match_query["$or"] = [
                    {"visibility": "public"},  # Bài viết công khai
                    {"visibility": "friends"}   # Bài viết bạn bè
                ]
            else:
                # Không phải bạn bè, chỉ xem public
                match_query["visibility"] = "public"
            
        elif is_own_profile:
            # Là chính chủ: hiển thị tất cả bài viết (không thêm điều kiện visibility)
            pass
        else:
            # Không có current_user, chỉ hiển thị public
            match_query["visibility"] = "public"

        print(f"Final match query: {match_query}")

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
            doc["author_name"] = author.get("full_name", author.get("username", "Người dùng"))
            doc["author_avatar"] = author.get("avatar_url")
            
            if "author_info" in doc:
                del doc["author_info"]
            
            posts.append(doc)

        print(f"Found {len(posts)} posts")
        return posts

    # In social_posts_service.py, update the get_feed method's pipeline
    async def get_feed(
        self,
        limit: int = 10,
        skip: int = 0,
        category: Optional[str] = None,
        current_user_id: Optional[str] = None
    ) -> List[dict]:
        try:
            # Xây dựng query cơ bản
            match_query = {
                "is_active": True,
                "is_permanently_deleted": False,
                "author_type": {"$in": ["user", "admin"]}  # Cho phép cả user và admin
            }
            
            # Lọc theo category
            if category and category != "general":
                match_query["product_category"] = category
            
            # Xử lý visibility dựa trên user hiện tại
            if current_user_id:
                try:
                    user_exists = await self.user_collection.find_one({"_id": ObjectId(current_user_id)})
                    if not user_exists:
                        # Fallback: chỉ hiển thị public
                        match_query["visibility"] = "public"
                    else:
                        # Lấy danh sách bạn bè
                        following = await self.db["follows"].find({
                            "user_id": ObjectId(current_user_id),
                            "status": "accepted"
                        }).to_list(length=None)
                        friend_ids = [ObjectId(f["target_id"]) for f in following]
                        friend_ids.append(ObjectId(current_user_id))
                        
                        # QUAN TRỌNG: Đảm bảo visibility logic hoạt động đúng
                        match_query["$or"] = [
                            {"visibility": "public"},  # Bài viết công khai (bao gồm của admin)
                            {"author_id": ObjectId(current_user_id)},  # Bài viết của chính user
                            {
                                "visibility": "friends",
                                "author_id": {"$in": friend_ids}
                            }
                        ]
                except Exception as e:
                    print(f"Error processing friends: {e}")
                    match_query["visibility"] = "public"
            else:
                # Không có user, chỉ hiển thị public
                match_query["visibility"] = "public"

            print(f"Final match query: {match_query}")

            # Thực hiện aggregation
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
                },
                {
                    "$project": {
                        "_id": {"$toString": "$_id"},
                        "author_id": {"$toString": "$author_id"},
                        "author_type": "$author_type",
                        "author_name": {
                            "$ifNull": [
                                "$author_info.full_name",
                                "$author_info.username",
                                "Người dùng"
                            ]
                        },
                        "author_avatar": "$author_info.avatar_url",
                        "content": 1,
                        "images": 1,
                        "videos": 1,
                        "tags": 1,
                        "location": 1,
                        "visibility": 1,
                        "post_type": 1,
                        "product_category": 1,
                        "allow_comment": 1,
                        "allow_share": 1,
                        "stats": 1,
                        "created_at": 1,
                        "updated_at": 1,
                        "is_active": 1,
                        "is_approved": 1,
                        "is_pinned": 1,
                        "report_count": 1,
                        "feed_score": 1,
                    }
                }
            ]

            cursor = self.collection.aggregate(pipeline)
            posts = []
            
            async for doc in cursor:
                if "stats" not in doc:
                    doc["stats"] = {
                        "like_count": 0,
                        "comment_count": 0,
                        "share_count": 0,
                        "save_count": 0,
                        "view_count": 0
                    }
                
                if "author_type" not in doc or not doc["author_type"]:
                    doc["author_type"] = "user"
                
                posts.append(doc)

            print(f"Found {len(posts)} posts in feed")
            
            # Debug: In ra danh sách author_id để kiểm tra
            for post in posts:
                print(f"Post ID: {post['_id']}, Author ID: {post['author_id']}, Author Type: {post['author_type']}")
            
            return posts
            
        except Exception as e:
            print(f"Error in get_feed: {e}")
            import traceback
            traceback.print_exc()
            return []
    async def update_post(
        self,
        post_id: str,
        user_id: str,
        update_data: SocialPostUpdate
    ) -> Optional[dict]:
        # Không cho phép sửa bài viết đã bị xóa
        query = {
            "_id": ObjectId(post_id),
            "author_id": ObjectId(user_id),
            "is_permanently_deleted": False
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
            author = await self.user_collection.find_one({"_id": ObjectId(updated_post["author_id"])})
            if author:
                updated_post["author_name"] = author.get("full_name", "Người dùng")
                updated_post["author_avatar"] = author.get("avatar_url")

        return updated_post

    async def delete_post(self, post_id: str, user_id: str) -> bool:
        """
        Xóa tạm thời bài viết: set is_active = False và ghi lại thời gian xóa
        """
        # Lấy bài viết
        post = await self.collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            return False
        
        # Chỉ cho phép xóa nếu bài viết chưa bị xóa vĩnh viễn
        if post.get("is_permanently_deleted", False):
            return False
        
        result = await self.collection.update_one(
            {
                "_id": ObjectId(post_id),
                "author_id": ObjectId(user_id)
            },
            {
                "$set": {
                    "is_active": False,
                    "deleted_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            # Giảm posts_count của user đi 1
            await self.user_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"posts_count": -1}}
            )
            return True
        
        return False

    # Thêm vào cuối class SocialPostService
    async def permanently_delete_expired_posts(self):
        """
        Xóa vĩnh viễn các bài viết đã bị xóa tạm thời quá 10 ngày
        """
        cutoff_date = datetime.utcnow() - timedelta(days=10)
        
        # Tìm các bài viết đã bị xóa tạm thời quá 10 ngày
        expired_posts = await self.collection.find({
            "is_active": False,
            "deleted_at": {"$lt": cutoff_date},
            "is_permanently_deleted": False
        }).to_list(length=None)
        
        deleted_count = 0
        for post in expired_posts:
            # Xóa vĩnh viễn bài viết
            result = await self.collection.delete_one({"_id": post["_id"]})
            if result.deleted_count > 0:
                deleted_count += 1
        
        return deleted_count

    async def get_post_by_id(self, post_id: str) -> Optional[dict]:
        """Lấy bài viết theo ID (chỉ lấy bài chưa xóa vĩnh viễn)"""
        try:
            pipeline = [
                {"$match": {
                    "_id": ObjectId(post_id),
                    "is_permanently_deleted": False
                }},
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
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                doc["author_id"] = str(doc["author_id"])
                author = doc.get("author_info", {})
                doc["author_name"] = author.get("full_name", "Người dùng")
                doc["author_avatar"] = author.get("avatar_url")
                if "author_info" in doc:
                    del doc["author_info"]
                return doc
            
            return None
        except Exception as e:
            print(f"Error getting post by id: {e}")
            return None

    async def get_all_posts_admin(self, filter_query: dict, skip: int = 0, limit: int = 20):
        # Admin có thể xem cả bài đã xóa tạm thời
        pipeline = [
            {"$match": filter_query},
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
            doc["author_name"] = author.get("full_name", "Người dùng")
            doc["author_avatar"] = author.get("avatar_url")
            posts.append(doc)
        
        return posts

    async def update_post_admin(self, post_id: str, update_data: dict):
        update_data["updated_at"] = datetime.utcnow()
        
        updated_post = await self.collection.find_one_and_update(
            {"_id": ObjectId(post_id)},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )
        
        if updated_post:
            updated_post["_id"] = str(updated_post["_id"])
            updated_post["author_id"] = str(updated_post["author_id"])
            
            author = await self.user_collection.find_one({"_id": ObjectId(updated_post["author_id"])})
            if author:
                updated_post["author_name"] = author.get("full_name", "Người dùng")
                updated_post["author_avatar"] = author.get("avatar_url")
            
            return updated_post
        
        return None

    async def delete_post_admin(self, post_id: str):
        """
        Admin có thể xóa vĩnh viễn bài viết ngay lập tức
        """
        result = await self.collection.delete_one({"_id": ObjectId(post_id)})
        return result.deleted_count > 0