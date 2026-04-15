# app/services/favorite_service.py
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

class FavoriteService:
    def __init__(self, db):
        self.db = db
        self.collection = db["favorites"]
        
        # Tạo indexes để tối ưu query
        self._create_indexes()
    
    def _create_indexes(self):
        """Tạo indexes để tối ưu truy vấn"""
        try:
            # Index cho user_id + product_id (unique) - ngăn trùng lặp
            self.collection.create_index(
                [("user_id", 1), ("product_id", 1)], 
                unique=True
            )
            # Index cho product_id (để đếm số lượng thích nhanh)
            self.collection.create_index([("product_id", 1)])
            # Index cho user_id (để lấy danh sách user)
            self.collection.create_index([("user_id", 1)])
            # Index cho created_at (nếu cần lọc theo thời gian)
            self.collection.create_index([("created_at", -1)])
        except Exception as e:
            print(f"Index creation warning: {e}")

    async def add_favorite(self, user_id: str, product_id: str) -> dict:
        """Thêm sản phẩm vào danh sách yêu thích"""
        try:
            favorite_doc = {
                "user_id": ObjectId(user_id),
                "product_id": ObjectId(product_id),
                "created_at": datetime.utcnow()
            }
            
            result = await self.collection.insert_one(favorite_doc)
            
            # Convert ObjectId sang string
            return {
                "_id": str(result.inserted_id),
                "user_id": user_id,
                "product_id": product_id,
                "created_at": favorite_doc["created_at"]
            }
        except Exception as e:
            # Duplicate key error - sản phẩm đã được yêu thích
            if "duplicate key" in str(e):
                return None
            raise e

    async def remove_favorite(self, user_id: str, product_id: str) -> bool:
        """Xóa sản phẩm khỏi danh sách yêu thích"""
        result = await self.collection.delete_one({
            "user_id": ObjectId(user_id),
            "product_id": ObjectId(product_id)
        })
        return result.deleted_count > 0

    async def is_favorite(self, user_id: str, product_id: str) -> bool:
        """Kiểm tra sản phẩm có trong danh sách yêu thích không"""
        count = await self.collection.count_documents({
            "user_id": ObjectId(user_id),
            "product_id": ObjectId(product_id)
        })
        return count > 0

    async def get_user_favorites(self, user_id: str, skip: int = 0, limit: int = 20) -> List[dict]:
        """Lấy danh sách sản phẩm yêu thích của user"""
        pipeline = [
            {"$match": {"user_id": ObjectId(user_id)}},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {"$lookup": {
                "from": "products",
                "localField": "product_id",
                "foreignField": "_id",
                "as": "product"
            }},
            {"$unwind": "$product"},
            {"$addFields": {
                "product_id_str": {"$toString": "$product_id"},
                "user_id_str": {"$toString": "$user_id"},
                "product_id_obj": "$product_id",
                "user_id_obj": "$user_id"
            }}
        ]
        
        cursor = self.collection.aggregate(pipeline)
        favorites = []
        
        async for doc in cursor:
            # Convert các ObjectId sang string
            favorite = {
                "_id": str(doc["_id"]),
                "user_id": str(doc["user_id"]),
                "product_id": str(doc["product_id"]),
                "created_at": doc["created_at"],
                "product": {
                    "id": str(doc["product"]["_id"]),
                    "_id": str(doc["product"]["_id"]),
                    "name": doc["product"].get("name", ""),
                    "description": doc["product"].get("description", ""),
                    "price": doc["product"].get("price", 0),
                    "stock": doc["product"].get("stock", 0),
                    "image_url": doc["product"].get("image_url", ""),
                    "origin": doc["product"].get("origin", ""),
                    "shop_id": str(doc["product"]["shop_id"]) if doc["product"].get("shop_id") else None,
                    "rating": doc["product"].get("rating", 4.5),
                    "created_at": doc["product"].get("created_at"),
                    "variants": []
                }
            }
            
            # Thêm variants nếu có
            if "variants" in doc["product"] and doc["product"]["variants"]:
                favorite["product"]["variants"] = [
                    {
                        "id": str(v["_id"]) if v.get("_id") else None,
                        "name": v.get("name", ""),
                        "price": v.get("price", 0),
                        "stock": v.get("stock", 0)
                    }
                    for v in doc["product"].get("variants", [])
                ]
            
            favorites.append(favorite)
        
        return favorites

    async def get_favorite_count(self, product_id: str) -> int:
        """Đếm số lượt yêu thích của sản phẩm - nhanh nhờ index"""
        return await self.collection.count_documents({
            "product_id": ObjectId(product_id)
        })

    async def get_favorites_by_products(self, user_id: str, product_ids: List[str]) -> dict:
        """Lấy map product_id -> is_favorite cho nhiều sản phẩm cùng lúc"""
        object_ids = [ObjectId(pid) for pid in product_ids]
        cursor = self.collection.find({
            "user_id": ObjectId(user_id),
            "product_id": {"$in": object_ids}
        })
        
        favorite_map = {pid: False for pid in product_ids}
        async for fav in cursor:
            favorite_map[str(fav["product_id"])] = True
        
        return favorite_map
    
    async def get_total_favorites_count(self, user_id: str) -> int:
        """Lấy tổng số sản phẩm yêu thích của user"""
        return await self.collection.count_documents({
            "user_id": ObjectId(user_id)
        })