from bson import ObjectId
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import HTTPException, status

class ReviewService:
    def __init__(self, db):
        self.db = db
        # Đổi tên collection để tránh trùng với bảng Reviews khác
        self.collection = db["product_reviews"]  # Thay đổi ở đây
        self.product_collection = db["products"]

    async def create_review(self, product_id: str, user_id: str, user_name: str, review_data: dict, user_avatar: Optional[str] = None):
        """Tạo đánh giá mới"""
        # Kiểm tra sản phẩm tồn tại
        product = await self.product_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")

        # Kiểm tra người dùng đã đánh giá sản phẩm này chưa
        existing_review = await self.collection.find_one({
            "product_id": ObjectId(product_id),
            "user_id": ObjectId(user_id)
        })
        
        if existing_review:
            raise HTTPException(status_code=400, detail="Bạn đã đánh giá sản phẩm này rồi")

        review = {
            "product_id": ObjectId(product_id),
            "user_id": ObjectId(user_id),
            "user_name": user_name,
            "user_avatar": user_avatar,
            "rating": review_data["rating"],
            "comment": review_data.get("comment"),
            "images": review_data.get("images", []),
            "status": "approved",  # Có thể đặt là pending nếu cần duyệt
            "helpful_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await self.collection.insert_one(review)
        review["_id"] = str(result.inserted_id)
        review["product_id"] = str(review["product_id"])
        review["user_id"] = str(review["user_id"])

        # Cập nhật rating trung bình cho sản phẩm
        await self._update_product_rating(product_id)

        return review

    async def get_reviews_by_product(
        self, 
        product_id: str, 
        skip: int = 0, 
        limit: int = 20,
        rating_filter: Optional[int] = None
    ):
        """Lấy danh sách đánh giá của sản phẩm"""
        query = {"product_id": ObjectId(product_id), "status": "approved"}
        
        if rating_filter and 1 <= rating_filter <= 5:
            query["rating"] = rating_filter

        total = await self.collection.count_documents(query)
        
        cursor = self.collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
        
        reviews = []
        async for review in cursor:
            review["_id"] = str(review["_id"])
            review["product_id"] = str(review["product_id"])
            review["user_id"] = str(review["user_id"])
            reviews.append(review)

        # Lấy thống kê đánh giá
        stats = await self.get_review_stats(product_id)

        return {
            "reviews": reviews,
            "total": total,
            "skip": skip,
            "limit": limit,
            "stats": stats
        }

    async def get_user_review(self, product_id: str, user_id: str):
        """Lấy đánh giá của user cho sản phẩm cụ thể"""
        review = await self.collection.find_one({
            "product_id": ObjectId(product_id),
            "user_id": ObjectId(user_id)
        })
        
        if review:
            review["_id"] = str(review["_id"])
            review["product_id"] = str(review["product_id"])
            review["user_id"] = str(review["user_id"])
        
        return review

    async def get_review_by_id(self, review_id: str):
        """Lấy đánh giá theo ID"""
        review = await self.collection.find_one({"_id": ObjectId(review_id)})
        if review:
            review["_id"] = str(review["_id"])
            review["product_id"] = str(review["product_id"])
            review["user_id"] = str(review["user_id"])
        return review

    async def update_review(self, review_id: str, user_id: str, update_data: dict):
        """Cập nhật đánh giá"""
        # Kiểm tra review tồn tại và thuộc về user
        review = await self.collection.find_one({
            "_id": ObjectId(review_id),
            "user_id": ObjectId(user_id)
        })
        
        if not review:
            raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá hoặc bạn không có quyền sửa")

        # Cập nhật
        update_data["updated_at"] = datetime.utcnow()
        await self.collection.update_one(
            {"_id": ObjectId(review_id)},
            {"$set": update_data}
        )

        # Cập nhật rating trung bình cho sản phẩm
        await self._update_product_rating(str(review["product_id"]))

        return await self.get_review_by_id(review_id)

    async def delete_review(self, review_id: str, user_id: str, is_admin: bool = False):
        """Xóa đánh giá"""
        query = {"_id": ObjectId(review_id)}
        if not is_admin:
            query["user_id"] = ObjectId(user_id)

        review = await self.collection.find_one(query)
        if not review:
            raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá hoặc bạn không có quyền xóa")

        product_id = str(review["product_id"])
        
        await self.collection.delete_one(query)

        # Cập nhật rating trung bình cho sản phẩm
        await self._update_product_rating(product_id)

        return {"message": "Xóa đánh giá thành công"}

    async def mark_helpful(self, review_id: str):
        """Đánh dấu đánh giá hữu ích"""
        result = await self.collection.update_one(
            {"_id": ObjectId(review_id)},
            {"$inc": {"helpful_count": 1}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá")
        
        return {"message": "Đã đánh dấu hữu ích"}

    async def get_review_stats(self, product_id: str) -> Dict:
        """Lấy thống kê đánh giá cho sản phẩm"""
        pipeline = [
            {"$match": {"product_id": ObjectId(product_id), "status": "approved"}},
            {"$group": {
                "_id": None,
                "average_rating": {"$avg": "$rating"},
                "total_reviews": {"$sum": 1},
                "rating_distribution": {
                    "$push": "$rating"
                }
            }}
        ]
        
        cursor = self.collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        
        if not result:
            return {
                "average_rating": 0,
                "total_reviews": 0,
                "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            }
        
        stats = result[0]
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for rating in stats.get("rating_distribution", []):
            if rating in distribution:
                distribution[rating] += 1
        
        return {
            "average_rating": round(stats["average_rating"], 1),
            "total_reviews": stats["total_reviews"],
            "rating_distribution": distribution
        }

    async def _update_product_rating(self, product_id: str):
        """Cập nhật rating trung bình cho sản phẩm"""
        stats = await self.get_review_stats(product_id)
        
        await self.product_collection.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {
                "average_rating": stats["average_rating"],
                "total_reviews": stats["total_reviews"]
            }}
        )

    async def get_user_reviews(self, user_id: str, skip: int = 0, limit: int = 20):
        """Lấy tất cả đánh giá của người dùng"""
        query = {"user_id": ObjectId(user_id)}
        
        total = await self.collection.count_documents(query)
        
        cursor = self.collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
        
        reviews = []
        async for review in cursor:
            review["_id"] = str(review["_id"])
            review["product_id"] = str(review["product_id"])
            review["user_id"] = str(review["user_id"])
            
            # Lấy thông tin sản phẩm
            product = await self.product_collection.find_one({"_id": ObjectId(review["product_id"])})
            if product:
                review["product_name"] = product.get("name", "")
                review["product_image"] = product.get("image_url", "")
            
            reviews.append(review)
        
        return {
            "reviews": reviews,
            "total": total,
            "skip": skip,
            "limit": limit
        }