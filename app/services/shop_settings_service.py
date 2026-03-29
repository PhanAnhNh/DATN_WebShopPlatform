# app/services/shop_settings_service.py
from bson import ObjectId
from datetime import datetime
from typing import Optional, Dict

class ShopSettingsService:
    def __init__(self, db):
        self.db = db
        self.collection = db["shop_settings"]
        self.shops_collection = db["shops"]

    async def get_settings(self, shop_id: str) -> Optional[Dict]:
        """Lấy toàn bộ cài đặt của shop"""
        settings = await self.collection.find_one({"shop_id": ObjectId(shop_id)})
        
        if not settings:
            settings = await self.create_default_settings(shop_id)
        
        # Convert ObjectId sang string
        settings["_id"] = str(settings["_id"])
        settings["shop_id"] = str(settings["shop_id"])
        
        return settings

    async def create_default_settings(self, shop_id: str) -> Dict:
        """Tạo cài đặt mặc định cho shop mới"""
        shop = await self.shops_collection.find_one({"_id": ObjectId(shop_id)})
        
        default_settings = {
            "shop_id": ObjectId(shop_id),
            "general": {
                "shop_name": shop.get("name", "Cửa hàng của tôi"),
                "shop_email": shop.get("email", ""),
                "shop_phone": shop.get("phone", ""),
                "shop_address": shop.get("address", ""),
                "tax_code": "",
                "website": "",
                "working_hours": "8:00 - 22:00",
                "timezone": "Asia/Ho_Chi_Minh",
                "date_format": "dd/mm/yyyy",
                "currency": "VND",
                "language": "vi"
            },
            "notifications": {
                "email_notifications": True,
                "sms_notifications": False,
                "order_created": True,
                "order_paid": True,
                "order_shipped": True,
                "order_completed": True,
                "order_cancelled": True,
                "return_requested": True,
                "return_processed": True,
                "low_stock_alert": True,
                "low_stock_threshold": 10,
                "new_review": True,
                "new_customer": False,
                "daily_report": True,
                "weekly_report": False,
                "monthly_report": True
            },
            "payment": {
                "cod": True,
                "bank_transfer": True,
                "momo": False,
                "vnpay": False,
                "zalopay": False,
                "bank_accounts": [],
                "momo_info": None,
                "auto_confirm_payment": True,
                "payment_timeout": 24
            },
            "shipping": {
                "free_shipping_threshold": 500000,
                "shipping_fee": 30000,
                "shipping_methods": [
                    {"id": "standard", "name": "Giao hàng tiêu chuẩn", "fee": 30000, "days": "3-5 ngày"},
                    {"id": "fast", "name": "Giao hàng nhanh", "fee": 50000, "days": "1-2 ngày"}
                ],
                "supported_provinces": ["Hồ Chí Minh", "Hà Nội", "Đà Nẵng", "Cần Thơ", "Hải Phòng"],
                "default_province": "Hồ Chí Minh",
                "allow_international": False
            },
            "security": {
                "two_factor_auth": False,
                "login_attempts": 5,
                "session_timeout": 30,
                "password_expiry": 90,
                "ip_whitelist": [],
                "allow_multiple_sessions": True,
                "require_strong_password": True
            },
            "invoice": {
                "show_logo": True,
                "show_tax_code": True,
                "show_phone": True,
                "show_address": True,
                "show_bank_info": True,
                "invoice_prefix": "HD",
                "invoice_footer": "Cảm ơn quý khách đã mua hàng!",
                "auto_numbering": True,
                "next_invoice_number": 1001,
                "print_format": "A5",
                "email_invoice": True
            },
            "social": {
                "facebook": None,
                "instagram": None,
                "youtube": None,
                "twitter": None,
                "whatsapp": None,
                "zalo": None,
                "show_social_links": True
            },
            "seo": {
                "meta_title": None,
                "meta_description": None,
                "meta_keywords": None,
                "google_analytics": None,
                "facebook_pixel": None,
                "allow_indexing": True,
                "sitemap_enabled": True
            },
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(default_settings)
        default_settings["_id"] = str(result.inserted_id)
        default_settings["shop_id"] = str(shop_id)
        
        return default_settings

    async def update_general_settings(self, shop_id: str, data: dict) -> Dict:
        """Cập nhật cài đặt chung và đồng bộ với shops collection"""
        
        # 1. Cập nhật shop_settings
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {"$set": {
                "general": data,
                "updated_at": datetime.utcnow()
            }}
        )
        
        # 2. ĐỒNG BỘ DỮ LIỆU VỚI shops COLLECTION
        shop_update_data = {
            "name": data.get("shop_name"),
            "email": data.get("shop_email"),
            "phone": data.get("shop_phone"),
            "address": data.get("shop_address"),
            "updated_at": datetime.utcnow()
        }
        
        # Loại bỏ các field None
        shop_update_data = {k: v for k, v in shop_update_data.items() if v is not None}
        
        if shop_update_data:
            await self.shops_collection.update_one(
                {"_id": ObjectId(shop_id)},
                {"$set": shop_update_data}
            )
        
        return await self.get_settings(shop_id)

    # Các method khác giữ nguyên...
    async def update_notification_settings(self, shop_id: str, data: dict) -> Dict:
        """Cập nhật cài đặt thông báo"""
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {"$set": {
                "notifications": data,
                "updated_at": datetime.utcnow()
            }}
        )
        return await self.get_settings(shop_id)

    async def update_payment_settings(self, shop_id: str, data: dict) -> Dict:
        """Cập nhật cài đặt thanh toán"""
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {"$set": {
                "payment": data,
                "updated_at": datetime.utcnow()
            }}
        )
        return await self.get_settings(shop_id)

    async def update_shipping_settings(self, shop_id: str, data: dict) -> Dict:
        """Cập nhật cài đặt vận chuyển"""
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {"$set": {
                "shipping": data,
                "updated_at": datetime.utcnow()
            }}
        )
        return await self.get_settings(shop_id)

    async def update_security_settings(self, shop_id: str, data: dict) -> Dict:
        """Cập nhật cài đặt bảo mật"""
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {"$set": {
                "security": data,
                "updated_at": datetime.utcnow()
            }}
        )
        return await self.get_settings(shop_id)

    async def update_invoice_settings(self, shop_id: str, data: dict) -> Dict:
        """Cập nhật cài đặt hóa đơn"""
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {"$set": {
                "invoice": data,
                "updated_at": datetime.utcnow()
            }}
        )
        return await self.get_settings(shop_id)

    async def update_social_settings(self, shop_id: str, data: dict) -> Dict:
        """Cập nhật cài đặt mạng xã hội"""
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {"$set": {
                "social": data,
                "updated_at": datetime.utcnow()
            }}
        )
        return await self.get_settings(shop_id)

    async def update_seo_settings(self, shop_id: str, data: dict) -> Dict:
        """Cập nhật cài đặt SEO"""
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {"$set": {
                "seo": data,
                "updated_at": datetime.utcnow()
            }}
        )
        return await self.get_settings(shop_id)