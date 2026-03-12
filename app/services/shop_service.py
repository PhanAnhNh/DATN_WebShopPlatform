from datetime import datetime
from bson import ObjectId
from app.models.shops_model import ShopCreate, ShopUpdate


class ShopService:
    def __init__(self, db):
        self.collection = db["shops"]

    # =========================
    # CREATE SHOP
    # =========================
    async def create_shop(self, shop_dict: dict):
        # Convert owner_id sang ObjectId
        if "owner_id" in shop_dict and shop_dict["owner_id"]:
            shop_dict["owner_id"] = ObjectId(shop_dict["owner_id"])

        shop_dict.update({
            "status": "active",
            "is_verified": False,
            "products_count": 0,
            "posts_count": 0,
            "followers_count": 0,
            "total_orders": 0,
            "total_revenue": 0,
            "view_count": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })

        result = await self.collection.insert_one(shop_dict)
        
        # Lấy shop vừa tạo và convert ObjectId sang string
        shop = await self.collection.find_one({"_id": result.inserted_id})
        if shop:
            shop["_id"] = str(shop["_id"])
            if "owner_id" in shop:
                shop["owner_id"] = str(shop["owner_id"])
        
        return shop

    # =========================
    # GET SHOP BY ID
    # =========================
    async def get_shop_by_id(self, shop_id: str):
        shop = await self.collection.find_one({"_id": ObjectId(shop_id)})
        if shop:
            shop["_id"] = str(shop["_id"])
            if "owner_id" in shop:
                shop["owner_id"] = str(shop["owner_id"])
        return shop

    # =========================
    # UPDATE SHOP
    # =========================
    async def update_shop(self, shop_id: str, shop_in: ShopUpdate):
        update_data = {k: v for k, v in shop_in.model_dump().items() if v is not None}
        update_data["updated_at"] = datetime.utcnow()

        await self.collection.update_one(
            {"_id": ObjectId(shop_id)},
            {"$set": update_data}
        )
        return await self.get_shop_by_id(shop_id)

    # =========================
    # LIST SHOPS
    # =========================
    async def list_shops(self, skip: int = 0, limit: int = 20):
        cursor = self.collection.find().skip(skip).limit(limit)
        shops = []
        async for shop in cursor:  # SỬA: dùng async for thay vì to_list
            shop["_id"] = str(shop["_id"])
            if "owner_id" in shop:
                shop["owner_id"] = str(shop["owner_id"])
            shops.append(shop)
        return shops

    # =========================
    # DASHBOARD STATS
    # =========================
    async def get_shop_dashboard(self, shop_id: str):
        shop = await self.get_shop_by_id(shop_id)
        if not shop:
            return None

        return {
            "products": shop["products_count"],
            "posts": shop["posts_count"],
            "followers": shop["followers_count"],
            "orders": shop["total_orders"],
            "revenue": shop["total_revenue"],
            "views": shop["view_count"],
        }