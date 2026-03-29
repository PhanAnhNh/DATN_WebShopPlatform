from datetime import datetime, timedelta


class AdminService:

    def __init__(self, db):
        self.db = db

    async def get_dashboard_stats(self):

        users = await self.db["users"].count_documents({})
        shops = await self.db["shops"].count_documents({})
        posts = await self.db["social_posts"].count_documents({})
        reports = await self.db["reports"].count_documents({})

        return {
            "total_users": users,
            "total_shops": shops,
            "total_posts": posts,
            "total_reports": reports
        }
    
    async def get_category_stats(self):
        pipeline = [
            {"$match": {"product_category": {"$exists": True, "$ne": None}}},  # chỉ lấy bài có category
            {
                "$group": {
                    "_id": "$product_category",
                    "count": {"$sum": 1}
                }
            }
        ]

        result = []
        total_posts = await self.db["social_posts"].count_documents({})

        async for item in self.db["social_posts"].aggregate(pipeline):
            percentage = (item["count"] / total_posts) * 100 if total_posts > 0 else 0
            # Chuyển đổi category code thành tên hiển thị (nếu cần)
            category_name = item["_id"]
            if category_name == "agriculture":
                category_name = "Nông Sản"
            elif category_name == "seafood":
                category_name = "Hải Sản"
            elif category_name == "specialty":
                category_name = "Đặc Sản"
            else:
                category_name = "Chung"

            result.append({
                "category": category_name,
                "count": item["count"],
                "percentage": round(percentage, 2)
            })

        return result

    async def get_new_users(self):

        last_week = datetime.utcnow() - timedelta(days=7)

        users = self.db["users"].find(
            {"created_at": {"$gte": last_week}}
        ).sort("created_at", -1)

        result = []

        async for u in users:
            u["_id"] = str(u["_id"])
            result.append(u)

        return result

    async def get_new_shops(self):
        """Lấy danh sách cửa hàng mới nhất (10 shop)"""
        try:
            shops = self.db["shops"].find().sort("created_at", -1).limit(10)
            result = []
            async for s in shops:
                # Chuyển tất cả ObjectId thành string
                shop_dict = {
                    "_id": str(s["_id"]),
                    "name": s.get("name", ""),
                    "owner_id": str(s.get("owner_id")) if s.get("owner_id") else None,
                    "created_at": s.get("created_at"),
                    "status": s.get("status", ""),
                    "is_verified": s.get("is_verified", False),
                    # thêm các trường cần thiết khác
                }
                # Lấy thông tin chủ shop
                owner = await self.db["users"].find_one({"_id": s.get("owner_id")})
                if owner:
                    shop_dict["owner_name"] = owner.get("full_name") or owner.get("username")
                else:
                    shop_dict["owner_name"] = "Chủ shop"
                result.append(shop_dict)
            return result
        except Exception as e:
            print(f"Lỗi khi lấy danh sách shop mới: {e}")
            return []
        
    async def get_visit_stats(self, days: int = 7):
        """Thống kê lượt truy cập (dựa trên view_count của bài viết)"""
        now = datetime.utcnow()
        start_date = now - timedelta(days=days)
        
        # Tạo mảng các ngày
        date_list = []
        for i in range(days):
            date = now - timedelta(days=i)
            date_str = date.strftime("%d/%m")
            date_list.append({"date": date, "date_str": date_str, "views": 0})
        
        # Aggregation: nhóm bài viết theo ngày, tính tổng view_count
        pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"}
                },
                "total_views": {"$sum": "$stats.view_count"}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}
        ]
        
        result = []
        async for doc in self.db["social_posts"].aggregate(pipeline):
            # Tạo datetime từ year, month, day
            d = datetime(doc["_id"]["year"], doc["_id"]["month"], doc["_id"]["day"])
            result.append({
                "date": d.strftime("%d/%m"),
                "views": doc["total_views"]
            })
        
        # Điền đủ các ngày
        final_result = []
        for item in date_list:
            found = next((x for x in result if x["date"] == item["date_str"]), None)
            if found:
                final_result.append({"name": item["date_str"], "value": found["views"]})
            else:
                final_result.append({"name": item["date_str"], "value": 0})
        
        # Sắp xếp theo thứ tự ngày tăng dần
        final_result.reverse()
        return final_result
    
    async def get_total_interactions(self, days: int = 7):
        """Tổng lượt tương tác (view + like + comment) của bài viết trong N ngày qua"""
        start_date = datetime.utcnow() - timedelta(days=days)
        pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"}
                },
                "total_views": {"$sum": "$stats.view_count"},
                "total_likes": {"$sum": "$stats.like_count"},
                "total_comments": {"$sum": "$stats.comment_count"}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}
        ]
        
        result = []
        async for doc in self.db["social_posts"].aggregate(pipeline):
            total = doc["total_views"] + doc["total_likes"] + doc["total_comments"]
            d = datetime(doc["_id"]["year"], doc["_id"]["month"], doc["_id"]["day"])
            result.append({
                "date": d.strftime("%d/%m"),
                "interactions": total
            })
        return result