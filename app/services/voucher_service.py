from bson import ObjectId
from datetime import datetime


class VoucherService:

    def __init__(self, db):
        self.collection = db["vouchers"]  # SỬA: dùng string key
        self.user_voucher = db["user_vouchers"]  # SỬA: dùng string key

    async def create_voucher(self, data: dict):
        # Convert các ObjectId nếu có
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
            "saved_at": datetime.utcnow()  # THÊM: thời gian lưu
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

    async def validate_voucher(self, code: str, order_total: float):
        voucher = await self.collection.find_one({
            "code": code,
            "status": "active"
        })

        if not voucher:
            return {"error": "Invalid voucher"}

        if voucher["end_date"] < datetime.utcnow():
            return {"error": "Voucher expired"}

        if voucher.get("usage_limit") and voucher["used_count"] >= voucher["usage_limit"]:
            return {"error": "Voucher usage limit reached"}  # THÊM: kiểm tra giới hạn sử dụng

        if order_total < voucher["min_order_value"]:
            return {"error": "Order not eligible"}

        discount = 0

        if voucher["discount_type"] == "percent":
            discount = order_total * voucher["discount_value"] / 100

            if voucher.get("max_discount"):
                discount = min(discount, voucher["max_discount"])

        else:
            discount = voucher["discount_value"]

        # Convert ObjectId sang string trước khi return
        voucher["_id"] = str(voucher["_id"])
        if "shop_id" in voucher and voucher["shop_id"]:
            voucher["shop_id"] = str(voucher["shop_id"])
        if "product_id" in voucher and voucher["product_id"]:
            voucher["product_id"] = str(voucher["product_id"])

        return {
            "discount": discount,
            "voucher": voucher
        }

    async def increase_usage(self, voucher_id: str):
        await self.collection.update_one(
            {"_id": ObjectId(voucher_id)},
            {"$inc": {"used_count": 1}}
        )
        return {"status": "success"}