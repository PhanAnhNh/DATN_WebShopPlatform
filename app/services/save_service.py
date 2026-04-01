# app/services/save_service.py
from bson import ObjectId
from datetime import datetime
from typing import List, Optional, Dict
from app.models.save_model import SavedPostCreate


class SaveService:
    def __init__(self, db):
        self.collection = db["saved_posts"]
        self.posts_collection = db["social_posts"]
    
    async def save_post(self, user_id: str, data: SavedPostCreate) -> Optional[dict]:
        """
        Lưu bài viết
        """
        # Kiểm tra bài viết có tồn tại không
        try:
            post = await self.posts_collection.find_one({"_id": ObjectId(data.post_id)})
        except:
            return None
            
        if not post:
            return None
        
        # Kiểm tra đã lưu chưa
        existing = await self.collection.find_one({
            "user_id": ObjectId(user_id),
            "post_id": ObjectId(data.post_id)
        })
        
        if existing:
            # Nếu đã lưu rồi thì trả về thông tin đã lưu
            existing["_id"] = str(existing["_id"])
            existing["user_id"] = str(existing["user_id"])
            existing["post_id"] = str(existing["post_id"])
            return existing
        
        # Tạo bản ghi mới
        save_data = {
            "user_id": ObjectId(user_id),
            "post_id": ObjectId(data.post_id),
            "note": data.note,
            "created_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(save_data)
        
        # Lấy lại bản ghi vừa tạo
        saved = await self.collection.find_one({"_id": result.inserted_id})
        
        # Tăng saved_count trong post stats (nếu có field stats)
        await self.posts_collection.update_one(
            {"_id": ObjectId(data.post_id)},
            {"$inc": {"stats.saved_count": 1}}
        )
        
        if saved:
            saved["_id"] = str(saved["_id"])
            saved["user_id"] = str(saved["user_id"])
            saved["post_id"] = str(saved["post_id"])
        
        return saved
    
    async def unsave_post(self, user_id: str, post_id: str) -> bool:
        """
        Bỏ lưu bài viết
        """
        result = await self.collection.delete_one({
            "user_id": ObjectId(user_id),
            "post_id": ObjectId(post_id)
        })
        
        if result.deleted_count > 0:
            # Giảm saved_count trong post stats
            await self.posts_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$inc": {"stats.saved_count": -1}}
            )
            return True
        
        return False
    
    async def check_saved(self, user_id: str, post_id: str) -> bool:
        """
        Kiểm tra bài viết đã được lưu chưa
        """
        try:
            saved = await self.collection.find_one({
                "user_id": ObjectId(user_id),
                "post_id": ObjectId(post_id)
            })
            return saved is not None
        except:
            return False
    
    async def get_saved_posts(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> List[Dict]:
        """
        Lấy danh sách bài viết đã lưu của user
        """
        saved_posts = []
        
        cursor = self.collection.find(
            {"user_id": ObjectId(user_id)}
        ).sort("created_at", -1).skip(skip).limit(limit)
        
        async for saved in cursor:
            # Lấy thông tin chi tiết của bài viết
            post = await self.posts_collection.find_one({"_id": saved["post_id"]})
            
            if post:
                # Chuyển đổi ObjectId sang string
                post["_id"] = str(post["_id"])
                if "author_id" in post:
                    post["author_id"] = str(post["author_id"])
                if "shop_id" in post and post["shop_id"]:
                    post["shop_id"] = str(post["shop_id"])
                
                saved["_id"] = str(saved["_id"])
                saved["user_id"] = str(saved["user_id"])
                saved["post_id"] = str(saved["post_id"])
                saved["post"] = post
                
                saved_posts.append(saved)
        
        return saved_posts
    
    async def get_saved_count(self, post_id: str) -> int:
        """
        Lấy số lượng người lưu bài viết
        """
        try:
            return await self.collection.count_documents({"post_id": ObjectId(post_id)})
        except:
            return 0