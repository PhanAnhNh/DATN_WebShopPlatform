from datetime import datetime, timedelta
import keyword
from typing import List, Optional
from bson import ObjectId
from pymongo import ReturnDocument
from requests import post

from app.models.social_posts_model import SocialPostCreate, SocialPostUpdate
from app.services.admin_notification_service import AdminNotificationService
from app.services.ai_moderation_service import AIModerationService


class SocialPostService:

    def __init__(self, db):
        self.collection = db["social_posts"]
        self.user_collection = db["users"]
        self.db = db
        self.admin_notification_service = AdminNotificationService(db)
        self.ai_moderation = AIModerationService(db)
        self.ai_moderation.set_notification_service(self.admin_notification_service)

    async def create_post(self, post_data: SocialPostCreate, current_user) -> dict:
        """Tạo bài viết mới với kiểm duyệt AI"""
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
        new_post["is_active"] = True  # Sẽ được cập nhật sau kiểm duyệt
        new_post["is_approved"] = True
        new_post["is_pinned"] = False
        new_post["report_count"] = 0
        new_post["feed_score"] = 0.0
        new_post["deleted_at"] = None
        new_post["is_permanently_deleted"] = False
        
        # Thêm các field cho AI moderation
        new_post["hidden_by_ai"] = False
        new_post["ai_moderation_result"] = None
        new_post["hidden_at"] = None
        
        # Xử lý group post
        if post_data.group_id:
            new_post["group_id"] = ObjectId(post_data.group_id)
            new_post["is_group_post"] = True
            await self.db["groups"].update_one(
                {"_id": ObjectId(post_data.group_id)},
                {"$inc": {"post_count": 1}}
            )
        else:
            new_post["is_group_post"] = False

        result = await self.collection.insert_one(new_post)
        post_id = str(result.inserted_id)

        # Tăng posts_count của user
        await self.user_collection.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$inc": {"posts_count": 1}}
        )

        # ⭐ KIỂM DUYỆT BÀI VIẾT BẰNG AI ⭐
        content = post_data.content or ""
        image_urls = post_data.images or []
        
        was_hidden = await self.ai_moderation.process_and_hide_post_if_needed(
            post_id=post_id,
            content=content,
            image_urls=image_urls,
            author_id=str(current_user.id),
            author_name=current_user.full_name or current_user.username
        )
        
        # Nếu bài viết bị ẩn, cập nhật lại is_active trong response
        if was_hidden:
            new_post["is_active"] = False
            new_post["hidden_by_ai"] = True
        
        # Gửi thông báo cho các admin khác (không phải AI notification)
        admin_users = await self.user_collection.find({"role": "admin"}).to_list(length=None)
        
        author_name = current_user.full_name or current_user.username
        
        for admin in admin_users:
            # Chỉ gửi thông báo bài viết mới nếu không bị ẩn bởi AI
            if not was_hidden:
                await self.admin_notification_service.create_notification(
                    user_id=str(admin["_id"]),
                    type="new_post",
                    title="Bài viết mới được đăng",
                    message=f"{author_name} vừa đăng bài viết mới trong {'nhóm' if post_data.group_id else 'trang cá nhân'}: {content[:50] if content else '...'}",
                    reference_id=post_id
                )
            
        new_post["_id"] = str(result.inserted_id)
        new_post["author_id"] = str(new_post["author_id"])
        if new_post.get("group_id"):
            new_post["group_id"] = str(new_post["group_id"])
        
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
            
            friend_ids = []
            try:
                # Tìm các mối quan hệ bạn bè đã được chấp nhận
                friendships = await self.db["friends"].find({
                    "$or": [
                        {"user_id": current_user_id, "friend_id": user_id, "status": "accepted"},
                        {"user_id": user_id, "friend_id": current_user_id, "status": "accepted"}
                    ]
                }).to_list(length=None)
                
                is_friend = len(friendships) > 0
                print(f"Is friend: {is_friend}")
                
                if is_friend:
                    friend_ids = [ObjectId(current_user_id)]
            except Exception as e:
                print(f"Error getting friends: {e}")
            
            if is_friend:
                match_query["$or"] = [
                    {"visibility": "public"},
                    {"visibility": "friends"}
                ]
            else:
                match_query["visibility"] = "public"
            
        elif is_own_profile:
            pass
        else:
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
            },
            # THÊM STAGE NÀY ĐỂ CHUYỂN ĐỔI group_id TỪ ObjectId SANG string
            {
                "$addFields": {
                    "group_id": {"$toString": "$group_id"}
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

            post = await self.get_post_with_shared_info(doc)
            posts.append(post)

        print(f"Found {len(posts)} posts")
        return posts

    async def get_feed(
        self,
        limit: int = 10,
        skip: int = 0,
        category: Optional[str] = None,
        current_user_id: Optional[str] = None
    ) -> List[dict]:
        """
        Lấy feed với thuật toán ưu tiên:
        - Điểm số = (cùng nhóm? 3 : 0) + (bạn bè? 2 : 0) + (độ mới của bài viết)
        - Bài viết có điểm cao nhất lên đầu
        """
        try:
            # Lấy danh sách nhóm user đã tham gia
            user_group_ids = []
            friend_ids = []
            
            if current_user_id:
                try:
                    # Lấy danh sách nhóm user tham gia
                    groups_cursor = self.db["groups"].find({
                        "members": {
                            "$elemMatch": {
                                "user_id": current_user_id,
                                "role": {"$in": ["admin", "member"]}
                            }
                        },
                        "is_active": True
                    })
                    
                    async for group in groups_cursor:
                        user_group_ids.append(str(group["_id"]))
                        
                    print(f"📌 User {current_user_id} is a member of {len(user_group_ids)} groups")
                    
                    # Lấy danh sách bạn bè
                    friendships = await self.db["friends"].find({
                        "$or": [
                            {"user_id": current_user_id, "status": "accepted"},
                            {"friend_id": current_user_id, "status": "accepted"}
                        ]
                    }).to_list(length=None)
                    
                    for friendship in friendships:
                        if friendship["user_id"] == current_user_id:
                            friend_ids.append(friendship["friend_id"])
                        else:
                            friend_ids.append(friendship["user_id"])
                            
                    print(f"👥 User {current_user_id} has {len(friend_ids)} friends")
                    
                except Exception as e:
                    print(f"Error fetching user data: {e}")

            # Xây dựng query cơ bản
            match_query = {
                "is_active": True,
                "is_permanently_deleted": False,
                "author_type": {"$in": ["user", "admin"]}
            }
            
            # Thêm điều kiện ẩn bài viết bị báo cáo
            match_query["$or"] = [
                {"hidden_by_report": {"$ne": True}},
                {"hidden_by_report": {"$exists": False}}
            ]
            
            # Lọc theo category
            if category and category != "general":
                match_query["product_category"] = category
            
            # Điều kiện visibility (bài viết user có thể xem)
            if current_user_id:
                visibility_conditions = [
                    {"visibility": "public"},
                    {"author_id": ObjectId(current_user_id)},
                ]
                
                if friend_ids:
                    friend_object_ids = [ObjectId(fid) for fid in friend_ids]
                    visibility_conditions.append({
                        "visibility": "friends",
                        "author_id": {"$in": friend_object_ids}
                    })
                
                match_query["$or"] = visibility_conditions
            else:
                match_query["visibility"] = "public"
            
            print(f"🔍 Match query: {match_query}")
            
            # Lấy tất cả bài viết thỏa mãn (không giới hạn limit ở đây)
            cursor = self.collection.find(match_query)
            
            posts = []
            current_time = datetime.utcnow()
            
            async for post in cursor:
                # Chuyển đổi ObjectId sang string
                post["_id"] = str(post["_id"])
                post["author_id"] = str(post["author_id"])
                
                if post.get("group_id"):
                    post["group_id"] = str(post["group_id"])
                else:
                    post["group_id"] = None
                
                # Lấy thông tin tác giả
                author = await self.user_collection.find_one({"_id": ObjectId(post["author_id"])})
                if author:
                    post["author_name"] = author.get("full_name") or author.get("username", "Người dùng")
                    post["author_avatar"] = author.get("avatar_url")
                else:
                    post["author_name"] = "Người dùng"
                    post["author_avatar"] = None
                
                # ========== TÍNH ĐIỂM ƯU TIÊN ==========
                score = 0
                
                # 1. Yếu tố thời gian (0-10 điểm)
                post_age = (current_time - post["created_at"]).total_seconds() / 3600  # tuổi bài viết (giờ)
                # Bài mới đăng trong 24h: 10 điểm, càng cũ điểm càng thấp
                time_score = max(0, 10 - post_age / 2.4)  # Sau 24h = 0 điểm
                score += time_score
                
                # 2. Yếu tố bạn bè (2 điểm nếu là bạn bè)
                author_id_str = str(post["author_id"])
                if author_id_str in friend_ids:
                    score += 2
                    print(f"   +2 điểm (bạn bè) cho bài {post['_id']}")
                
                # 3. Yếu tố cùng nhóm (3 điểm nếu cùng nhóm)
                post_group_id = post.get("group_id")
                if post_group_id and str(post_group_id) in user_group_ids:
                    score += 3
                    print(f"   +3 điểm (cùng nhóm) cho bài {post['_id']}")
                
                # Lưu điểm
                post["feed_score"] = score
                posts.append(post)
                
                print(f"📊 Bài {post['_id'][-8:]}: time={time_score:.1f}, total={score:.1f}")
            
            # Sắp xếp theo điểm số giảm dần (cao nhất lên đầu)
            posts.sort(key=lambda x: x.get("feed_score", 0), reverse=True)
            
            # Áp dụng phân trang
            paginated_posts = posts[skip:skip + limit]
            
            # Lấy thông tin shared post (nếu có)
            final_posts = []
            for post in paginated_posts:
                final_post = await self.get_post_with_shared_info(post)
                final_posts.append(final_post)
            
            print(f"✅ Found {len(posts)} posts, returning {len(final_posts)} after pagination")
            
            return final_posts
            
        except Exception as e:
            print(f"Error in get_feed: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _get_public_group_ids(self) -> List[str]:
        """Lấy danh sách ID của các group công khai"""
        try:
            public_groups = await self.db["groups"].find({
                "privacy": "public",
                "is_active": True
            }).to_list(length=None)
            return [str(group["_id"]) for group in public_groups]
        except Exception as e:
            print(f"Error getting public group IDs: {e}")
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
                },
                {
                    "$project": {
                        "_id": {"$toString": "$_id"},
                        "author_id": {"$toString": "$author_id"},
                        "author_type": 1,
                        "author_name": {
                            "$ifNull": ["$author_info.full_name", "$author_info.username", "Người dùng"]
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
                        "shared_post_id": 1,  # QUAN TRỌNG: Phải include field này
                        "product_id": 1
                    }
                }
            ]
            
            cursor = self.collection.aggregate(pipeline)
            async for doc in cursor:
                # Đảm bảo shared_post_id được giữ nguyên
                if "shared_post_id" in doc:
                    print(f"Found shared_post_id in doc: {doc['shared_post_id']}")
                else:
                    print("No shared_post_id in doc")
                
                post = await self.get_post_with_shared_info(doc)
                return post
            
            return None
        except Exception as e:
            print(f"Error getting post by id: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def get_all_posts_admin(self, filter_query: dict, skip: int = 0, limit: int = 20):
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
            },
            # THÊM STAGE NÀY ĐỂ CHUYỂN ĐỔI ObjectId SANG string
            {
                "$addFields": {
                    "group_id": {"$toString": "$group_id"},
                    "author_id": {"$toString": "$author_id"}
                }
            }
        ]
        
        cursor = self.collection.aggregate(pipeline)
        posts = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            # Không cần convert ở đây nữa vì đã convert ở aggregate
            author = doc.get("author_info", {})
            doc["author_name"] = author.get("full_name", "Người dùng")
            doc["author_avatar"] = author.get("avatar_url")
            posts.append(doc)
        
        return posts
    async def update_post_admin(self, post_id: str, update_data: dict):
        """Admin cập nhật bài viết"""
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
    
    async def increment_view_count(self, post_id: str):
        await self.collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"stats.view_count": 1}}
        )

    async def get_post_with_shared_info(self, post: dict) -> dict:
        """Lấy bài viết kèm thông tin bài gốc nếu là bài chia sẻ"""
        # Kiểm tra nếu là bài chia sẻ và có shared_post_id
        if post.get("post_type") == "share" and post.get("shared_post_id"):
            try:
                shared_post_id = post.get("shared_post_id")
                print(f"Getting shared post with ID: {shared_post_id}")  # Debug log
                
                # Tìm bài viết gốc
                shared_post = await self.collection.find_one({
                    "_id": ObjectId(shared_post_id),
                    "is_permanently_deleted": False
                })
                
                if shared_post:
                    # Lấy thông tin tác giả bài gốc
                    author = await self.user_collection.find_one({"_id": shared_post["author_id"]})
                    post["shared_post"] = {
                        "_id": str(shared_post["_id"]),
                        "content": shared_post.get("content", ""),
                        "images": shared_post.get("images", []),
                        "author_name": author.get("full_name", author.get("username", "Người dùng")) if author else "Unknown",
                        "author_avatar": author.get("avatar_url") if author else None,
                        "created_at": shared_post.get("created_at")
                    }
                    print(f"Added shared_post to response: {post['shared_post']['_id']}")  # Debug log
                else:
                    print(f"Shared post not found for ID: {shared_post_id}")
            except Exception as e:
                print(f"Error getting shared post: {e}")
                import traceback
                traceback.print_exc()
        return post
    
    async def search_posts(
    self,
    keyword: str,
    limit: int = 20,
    current_user_id: Optional[str] = None
) -> List[dict]:
        """
        Tìm kiếm bài viết theo nội dung, tags và tên tác giả
        """
        try:
            # Tạo regex pattern cho tìm kiếm không phân biệt hoa thường
            regex_pattern = {"$regex": keyword, "$options": "i"}
            
            # Bước 1: Tìm users có tên khớp với keyword
            matching_user_ids = []
            try:
                matching_users = await self.user_collection.find({
                    "$or": [
                        {"full_name": regex_pattern},
                        {"username": regex_pattern}
                    ]
                }).to_list(length=None)
                
                matching_user_ids = [user["_id"] for user in matching_users]
                print(f"Found {len(matching_user_ids)} users matching '{keyword}'")
            except Exception as e:
                print(f"Error finding users: {e}")
            
            # Xây dựng query tìm kiếm bài viết
            search_conditions = [
                {"content": regex_pattern},  # Tìm trong nội dung
                {"tags": regex_pattern}      # Tìm trong tags
            ]
            
            # Thêm điều kiện tìm theo author_id nếu có user khớp
            if matching_user_ids:
                search_conditions.append({"author_id": {"$in": matching_user_ids}})
            
            search_query = {
                "$or": search_conditions,
                "is_active": True,
                "is_permanently_deleted": False,
                "author_type": {"$in": ["user", "admin"]}
            }
            
            # Tạo visibility conditions riêng
            visibility_conditions = []
            
            # Xử lý visibility dựa trên user hiện tại
            if current_user_id:
                try:
                    user_exists = await self.user_collection.find_one({"_id": ObjectId(current_user_id)})
                    if user_exists:
                        # Lấy danh sách bạn bè từ collection follows
                        following = await self.db["follows"].find({
                            "user_id": ObjectId(current_user_id),
                            "status": "accepted"
                        }).to_list(length=None)
                        friend_ids = [ObjectId(f["target_id"]) for f in following]
                        friend_ids.append(ObjectId(current_user_id))
                        
                        # Visibility conditions cho user đã đăng nhập
                        visibility_conditions = [
                            {"visibility": "public"},
                            {"author_id": ObjectId(current_user_id)},
                            {
                                "visibility": "friends",
                                "author_id": {"$in": friend_ids}
                            }
                        ]
                    else:
                        visibility_conditions = [{"visibility": "public"}]
                except Exception as e:
                    print(f"Error processing user for search: {e}")
                    visibility_conditions = [{"visibility": "public"}]
            else:
                visibility_conditions = [{"visibility": "public"}]
            
            # Thêm visibility vào query bằng $and
            if visibility_conditions:
                final_query = {
                    "$and": [
                        search_query,
                        {"$or": visibility_conditions}
                    ]
                }
            else:
                final_query = search_query
            
            print(f"Search query: {final_query}")
            
            # Pipeline aggregation
            pipeline = [
                {"$match": final_query},
                {"$sort": {"created_at": -1}},
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
                        "shared_post_id": 1,
                        "product_id": 1
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
                
                # Highlight keyword trong content
                if doc.get("content") and keyword.lower() in doc["content"].lower():
                    content_lower = doc["content"].lower()
                    keyword_lower = keyword.lower()
                    start_index = content_lower.find(keyword_lower)
                    if start_index != -1:
                        end_index = start_index + len(keyword)
                        highlighted = (
                            doc["content"][:start_index] + 
                            f'<mark style="background-color: #ffeb3b; padding: 0 2px; border-radius: 3px;">{doc["content"][start_index:end_index]}</mark>' + 
                            doc["content"][end_index:]
                        )
                        doc["content_highlighted"] = highlighted
                
                # Highlight tên tác giả nếu khớp
                author_name = doc.get("author_name", "")
                if keyword.lower() in author_name.lower():
                    author_lower = author_name.lower()
                    keyword_lower = keyword.lower()
                    start_index = author_lower.find(keyword_lower)
                    if start_index != -1:
                        end_index = start_index + len(keyword)
                        highlighted_author = (
                            author_name[:start_index] + 
                            f'<mark style="background-color: #4caf50; padding: 0 2px; border-radius: 3px; color: white;">{author_name[start_index:end_index]}</mark>' + 
                            author_name[end_index:]
                        )
                        doc["author_name_highlighted"] = highlighted_author
                
                if doc.get("tags"):
                    matching_tags = [tag for tag in doc["tags"] if keyword.lower() in tag.lower()]
                    if matching_tags:
                        doc["matching_tags"] = matching_tags
                
                post = await self.get_post_with_shared_info(doc)
                posts.append(post)
            
            print(f"Search found {len(posts)} posts for keyword: {keyword}")
            return posts
            
        except Exception as e:
            print(f"Error in search_posts: {e}")
            import traceback
            traceback.print_exc()
            return []
        