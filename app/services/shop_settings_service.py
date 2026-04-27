# app/services/shop_settings_service.py
from fileinput import filename
from io import BytesIO
import os
import uuid
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from bson import ObjectId
from datetime import datetime
from typing import Optional, Dict

import qrcode
from app.core.r2_config import R2Config

class ShopSettingsService:
    def __init__(self, db):
        self.db = db
        self.collection = db["shop_settings"]
        self.shops_collection = db["shops"]

    def get_r2_client(self):
        """Khởi tạo S3 client cho R2"""
        if not R2Config.ACCESS_KEY_ID or not R2Config.SECRET_ACCESS_KEY:
            raise ValueError("R2 credentials not configured! Check .env file")
        
        return boto3.client(
            "s3",
            endpoint_url=R2Config.ENDPOINT_URL,
            aws_access_key_id=R2Config.ACCESS_KEY_ID,
            aws_secret_access_key=R2Config.SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto"
        )

    async def upload_image_to_r2(self, file) -> Optional[str]:
        """Upload ảnh lên Cloudflare R2 và trả về URL công khai"""
        if not file:
            return None

        try:
            # Kiểm tra file có phải ảnh không
            if not file.content_type or not file.content_type.startswith("image/"):
                return None

            # Đọc nội dung file
            content = await file.read()
            
            # Tạo tên file unique
            file_extension = file.filename.split(".")[-1].lower()
            unique_filename = f"qr_codes/{uuid.uuid4()}.{file_extension}"
            
            # Upload lên R2
            s3 = self.get_r2_client()
            s3.put_object(
                Bucket=R2Config.BUCKET_NAME,
                Key=unique_filename,
                Body=content,
                ContentType=file.content_type,
                CacheControl="public, max-age=31536000"
            )
            
            # Tạo URL công khai
            public_url = f"{R2Config.PUBLIC_URL_BASE}/{unique_filename}"
            
            return public_url
            
        except Exception as e:
            print(f"Error uploading to R2: {e}")
            return None

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
    
    async def add_bank_account(self, shop_id: str, account_data: dict) -> Dict:
        """Thêm tài khoản ngân hàng mới"""
        # Tạo ID cho tài khoản
        account_id = str(uuid.uuid4())
        
        new_account = {
            "id": account_id,
            "bank_name": account_data.get("bank_name"),
            "bank_code": account_data.get("bank_code"),
            "account_number": account_data.get("account_number"),
            "account_name": account_data.get("account_name"),
            "branch": account_data.get("branch"),
            "qr_code_url": account_data.get("qr_code_url"),
            "is_active": account_data.get("is_active", True),
            "created_at": datetime.utcnow()
        }
        
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {
                "$push": {"payment.bank_accounts": new_account},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return new_account

    async def update_bank_account(self, shop_id: str, account_id: str, data: dict) -> Dict:
        """Cập nhật tài khoản ngân hàng"""
        # Xây dựng update object
        update_fields = {}
        for key in ["bank_name", "bank_code", "account_number", "account_name", "branch", "is_active"]:
            if key in data:
                update_fields[f"payment.bank_accounts.$.{key}"] = data[key]
        
        if data.get("qr_code_url"):
            update_fields["payment.bank_accounts.$.qr_code_url"] = data["qr_code_url"]
        
        update_fields["payment.bank_accounts.$.updated_at"] = datetime.utcnow()
        
        await self.collection.update_one(
            {
                "shop_id": ObjectId(shop_id),
                "payment.bank_accounts.id": account_id
            },
            {"$set": update_fields}
        )
        
        return await self.get_bank_account(shop_id, account_id)

    async def delete_bank_account(self, shop_id: str, account_id: str) -> Dict:
        """Xóa tài khoản ngân hàng"""
        await self.collection.update_one(
            {"shop_id": ObjectId(shop_id)},
            {"$pull": {"payment.bank_accounts": {"id": account_id}}}
        )
        
        return {"message": "Xóa tài khoản thành công"}

    async def get_bank_account(self, shop_id: str, account_id: str) -> Optional[Dict]:
        """Lấy thông tin một tài khoản ngân hàng"""
        settings = await self.collection.find_one(
            {"shop_id": ObjectId(shop_id)},
            {"payment.bank_accounts": {"$elemMatch": {"id": account_id}}}
        )
        
        if settings and settings.get("payment", {}).get("bank_accounts"):
            return settings["payment"]["bank_accounts"][0]
        return None

    async def upload_qr_code(self, shop_id: str, account_id: str, file) -> Dict:
        """Upload QR code lên Cloudflare R2 cho tài khoản ngân hàng"""
        
        # Upload ảnh lên R2
        uploaded_url = await self.upload_image_to_r2(file)
        if not uploaded_url:
            return {"error": "Không thể upload ảnh lên Cloudflare R2"}
        
        # Cập nhật URL vào database
        await self.collection.update_one(
            {
                "shop_id": ObjectId(shop_id),
                "payment.bank_accounts.id": account_id
            },
            {
                "$set": {
                    "payment.bank_accounts.$.qr_code_url": uploaded_url,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {"qr_code_url": uploaded_url}

    async def save_qr_url(self, shop_id: str, account_id: str, qr_code_url: str) -> Dict:
        """Lưu URL QR code (nhập tay) cho tài khoản ngân hàng"""
        
        # Cập nhật URL vào database
        await self.collection.update_one(
            {
                "shop_id": ObjectId(shop_id),
                "payment.bank_accounts.id": account_id
            },
            {
                "$set": {
                    "payment.bank_accounts.$.qr_code_url": qr_code_url,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {"qr_code_url": qr_code_url}

    async def delete_qr_code(self, shop_id: str, account_id: str) -> Dict:
        """Xóa QR code khỏi database"""
        await self.collection.update_one(
            {
                "shop_id": ObjectId(shop_id),
                "payment.bank_accounts.id": account_id
            },
            {
                "$set": {
                    "payment.bank_accounts.$.qr_code_url": None,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {"message": "Xóa mã QR thành công"}

    
    async def upload_bytes_to_r2(self, file_bytes: bytes, filename: str, content_type: str) -> Optional[str]:
        """Upload bytes trực tiếp lên R2"""
        try:
            s3 = self.get_r2_client()
            s3.put_object(
                Bucket=R2Config.BUCKET_NAME,
                Key=filename,
                Body=file_bytes,
                ContentType=content_type,
                CacheControl="public, max-age=31536000"
            )
            return f"{R2Config.PUBLIC_URL_BASE}/{filename}"
        except Exception as e:
            print(f"Error uploading to R2: {e}")
            return None
        
    async def generate_qr_code(self, order_code: str, amount: float, bank_account: dict) -> Optional[str]:
        """
        Tạo QR code cho đơn hàng, upload lên R2 và trả về URL công khai.
        bank_account: dict gồm account_number, account_name, bank_name
        """
        # Nội dung QR: chỉ chứa mã đơn hàng (để webhook dễ parse)
        content = order_code
        
        # Tạo QR
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Lưu vào BytesIO
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        file_bytes = buffer.getvalue()
        unique_name = f"qr_orders/{order_code}_{uuid.uuid4().hex}.png"
        uploaded_url = await self.upload_bytes_to_r2(file_bytes, unique_name, "image/png")
        return uploaded_url