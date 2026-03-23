# app/services/voucher_service.py
from bson import ObjectId
from datetime import datetime, timezone
from dateutil import parser

class VoucherService:

    def __init__(self, db):
        self.collection = db["vouchers"]
        self.user_voucher = db["user_vouchers"]

    async def create_voucher(self, data: dict):
        if "shop_id" in data and data["shop_id"]:
            data["shop_id"] = ObjectId(data["shop_id"])
        if "product_id" in data and data["product_id"]:
            data["product_id"] = ObjectId(data["product_id"])

        data["used_count"] = 0
        data["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(data)

        voucher = await self.collection.find_one({"_id": result.inserted_id})
        if voucher:
            voucher["_id"] = str(voucher["_id"])
            if "shop_id" in voucher and voucher["shop_id"]:
                voucher["shop_id"] = str(voucher["shop_id"])
            if "product_id" in voucher and voucher["product_id"]:
                voucher["product_id"] = str(voucher["product_id"])

        return voucher

    async def get_vouchers(self):
        vouchers = []

        cursor = self.collection.find({
            "status": "active"
        })

        async for v in cursor:
            v["_id"] = str(v["_id"])
            if "shop_id" in v and v["shop_id"]:
                v["shop_id"] = str(v["shop_id"])
            if "product_id" in v and v["product_id"]:
                v["product_id"] = str(v["product_id"])
            vouchers.append(v)

        return vouchers

    async def save_voucher(self, user_id: str, voucher_id: str):
        existing = await self.user_voucher.find_one({
            "user_id": user_id,
            "voucher_id": voucher_id
        })

        if existing:
            return {"message": "Voucher already saved"}

        await self.user_voucher.insert_one({
            "user_id": user_id,
            "voucher_id": voucher_id,
            "saved_at": datetime.utcnow()
        })

        return {"message": "Voucher saved"}

    async def get_user_vouchers(self, user_id: str):
        vouchers = []

        cursor = self.user_voucher.find({
            "user_id": user_id
        })

        async for v in cursor:
            v["_id"] = str(v["_id"])
            vouchers.append(v)

        return vouchers

    async def validate_voucher(self, code: str, order_total: float, user_id: str = None, shop_id: str = None):
        """
        Validate voucher với user và shop context
        """
        try:
            voucher = await self.collection.find_one({
                "code": code,
                "status": "active"
            })

            if not voucher:
                return {"error": "Invalid voucher"}

            
            # Kiểm tra target_type
            if voucher.get("target_type") == "shop":
                # Convert shop_id trong voucher sang string để so sánh
                voucher_shop_id = None
                if voucher.get("shop_id"):
                    # Nếu là ObjectId, convert sang string
                    if isinstance(voucher["shop_id"], ObjectId):
                        voucher_shop_id = str(voucher["shop_id"])
                    else:
                        voucher_shop_id = str(voucher["shop_id"])
                
                # Nếu không có shop_id từ frontend hoặc không khớp
                if not shop_id or voucher_shop_id != shop_id:
                    print(f"Shop ID mismatch: {voucher_shop_id} vs {shop_id}")
                    return {"error": "Voucher chỉ áp dụng cho shop cụ thể"}
            
            # Kiểm tra ngày hết hạn
            end_date = voucher.get("end_date")
            if not end_date:
                return {"error": "Voucher không có ngày hết hạn"}
                
            if isinstance(end_date, str):
                try:
                    end_date = parser.parse(end_date)
                except:
                    return {"error": "Invalid voucher date format"}
            
            # Remove timezone if present
            if hasattr(end_date, 'tzinfo') and end_date.tzinfo is not None:
                end_date = end_date.replace(tzinfo=None)
            
            current_time = datetime.utcnow()
            
            if end_date < current_time:
                return {"error": f"Voucher expired on {end_date.strftime('%d/%m/%Y')}"}

            # Kiểm tra số lần sử dụng
            if voucher.get("usage_limit") and voucher.get("used_count", 0) >= voucher.get("usage_limit"):
                return {"error": "Voucher usage limit reached"}

            # Kiểm tra đơn hàng tối thiểu
            min_order = voucher.get("min_order_value", 0)
            if order_total < min_order:
                return {"error": f"Đơn hàng phải từ {min_order:,.0f} VND"}

            # Tính giảm giá
            discount = 0
            discount_type = voucher.get("discount_type")
            discount_value = voucher.get("discount_value", 0)
            
            if discount_type == "percent":
                discount = order_total * discount_value / 100
                max_discount = voucher.get("max_discount")
                if max_discount:
                    discount = min(discount, max_discount)
            else:
                discount = discount_value

            # Convert ObjectId sang string cho response
            voucher_response = {
                "_id": str(voucher["_id"]),
                "code": voucher["code"],
                "discount_type": discount_type,
                "discount_value": discount_value,
                "min_order_value": voucher.get("min_order_value", 0),
                "max_discount": voucher.get("max_discount"),
                "usage_limit": voucher.get("usage_limit"),
                "used_count": voucher.get("used_count", 0),
                "target_type": voucher.get("target_type"),
                "start_date": voucher.get("start_date"),
                "end_date": voucher.get("end_date")
            }
            
            if voucher.get("shop_id"):
                voucher_response["shop_id"] = str(voucher["shop_id"]) if isinstance(voucher["shop_id"], ObjectId) else voucher["shop_id"]

            print(f"Validation successful! Discount: {discount}")
            
            return {
                "discount": discount,
                "voucher": voucher_response
            }
            
        except Exception as e:
            print(f"Error validating voucher: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": f"Lỗi server: {str(e)}"}

    async def increase_usage(self, voucher_id: str):
        try:
            await self.collection.update_one(
                {"_id": ObjectId(voucher_id)},
                {"$inc": {"used_count": 1}}
            )
            return {"status": "success"}
        except Exception as e:
            print(f"Error increasing usage: {str(e)}")
            return {"status": "error", "message": str(e)}