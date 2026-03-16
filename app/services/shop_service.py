from datetime import datetime
from bson import ObjectId
from app.models.shops_model import ShopCreate, ShopUpdate
from app.models.user_model import UserCreate
from app.services.user_service import UserService


class ShopService:
    def __init__(self, db):
        self.collection = db["shops"]
        self.user_service = UserService()

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
    # CREATE SHOP WITH OWNER
    # =========================
    async def create_shop_with_owner(self, shop_owner_data: dict):
        """
        Tạo đồng thời shop và tài khoản chủ shop
        """
        # 1. Tạo user (chủ shop) trước
        user_create = UserCreate(
            username=shop_owner_data["owner_username"],
            email=shop_owner_data["owner_email"],
            password=shop_owner_data["owner_password"],
            full_name=shop_owner_data.get("owner_full_name"),
            phone=shop_owner_data.get("owner_phone"),
            gender=shop_owner_data.get("owner_gender"),
            dob=shop_owner_data.get("owner_dob"),
            address=shop_owner_data.get("owner_address")
        )
        
        # Tạo user
        user_id = await self.user_service.create_user(user_create)
        if not user_id:
            return None, "Username hoặc Email đã tồn tại"
        
        # 2. Tạo shop với owner_id vừa tạo
        shop_dict = {
            "name": shop_owner_data["shop_name"],
            "slug": shop_owner_data["shop_slug"],
            "description": shop_owner_data.get("shop_description"),
            "phone": shop_owner_data.get("shop_phone"),
            "email": shop_owner_data.get("shop_email"),
            "address": shop_owner_data.get("shop_address"),
            "province": shop_owner_data.get("shop_province"),
            "district": shop_owner_data.get("shop_district"),
            "ward": shop_owner_data.get("shop_ward"),
            "logo_url": shop_owner_data.get("shop_logo_url"),
            "banner_url": shop_owner_data.get("shop_banner_url"),
            "owner_id": ObjectId(user_id),
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
        }
        
        result = await self.collection.insert_one(shop_dict)
        
        # 3. Cập nhật shop_id cho user
        await self.user_service.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"shop_id": str(result.inserted_id), "role": "shop_owner"}}
        )
        
        # 4. Lấy thông tin shop vừa tạo
        shop = await self.collection.find_one({"_id": result.inserted_id})
        if shop:
            shop["_id"] = str(shop["_id"])
            shop["owner_id"] = str(shop["owner_id"])
        
        # 5. Lấy thông tin user vừa tạo
        user = await self.user_service.get_user_by_id(user_id)
        
        return {
            "shop": shop,
            "owner": user,
            "login_info": {
                "username": shop_owner_data["owner_username"],
                "password": shop_owner_data["owner_password"],  # Chỉ trả về khi tạo
                "message": "Tài khoản đăng nhập đã được tạo"
            }
        }, None

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

    # app/services/shop_service.py

    async def update_shop_admin(self, shop_id: str, update_data):
        """Admin cập nhật shop - nhận cả model hoặc dict"""
        
        # Nếu update_data là model, lấy dict từ model
        if hasattr(update_data, 'model_dump'):
            update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        else:
            # Nếu update_data là dict, dùng trực tiếp
            update_dict = update_data
        
        update_dict["updated_at"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {"_id": ObjectId(shop_id)},
            {"$set": update_dict}
        )
        
        if result.modified_count > 0:
            return await self.get_shop_by_id(shop_id)
        return None

    async def update_shop_status_admin(self, shop_id: str, status: str):
        """Admin cập nhật trạng thái shop (dùng cho status riêng)"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.update_one(
            {"_id": ObjectId(shop_id)},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            return await self.get_shop_by_id(shop_id)
        return None
    
    async def delete_shop_admin(self, shop_id: str):
        """Admin xóa shop - XÓA HẲN (HARD DELETE) khỏi database"""
        result = await self.collection.delete_one({"_id": ObjectId(shop_id)})
        return result.deleted_count > 0