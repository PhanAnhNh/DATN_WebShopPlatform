
from bson import ObjectId
from datetime import datetime
from typing import Optional, Dict, List
from app.models.shipping_voucher_model import ShippingVoucherStatus, ShippingVoucherType

class ShippingVoucherService:
    def __init__(self, db):
        self.db = db
        self.collection = db["shipping_vouchers"]
        self.user_voucher = db["user_shipping_vouchers"]

    async def create_voucher(self, data: dict, shop_id: str = None) -> tuple:
        """Tạo voucher vận chuyển mới"""
        # Kiểm tra mã code trùng
        existing = await self.collection.find_one({
            "code": data["code"],
            "shipping_unit_id": ObjectId(data["shipping_unit_id"])
        })
        
        if existing:
            return None, "Mã voucher đã tồn tại"
        
        # Tạo voucher
        voucher_data = {
            "code": data["code"].upper(),
            "discount_type": data["discount_type"],
            "discount_value": data["discount_value"],
            "max_discount": data.get("max_discount"),
            "min_order_value": data.get("min_order_value", 0),
            "usage_limit": data.get("usage_limit"),
            "used_count": 0,
            "shipping_unit_id": ObjectId(data["shipping_unit_id"]),
            "start_date": data["start_date"],
            "end_date": data["end_date"],
            "status": ShippingVoucherStatus.active.value,
            "description": data.get("description"),
            "created_by": "shop" if shop_id else "admin",
            "shop_id": ObjectId(shop_id) if shop_id else None,
            "created_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(voucher_data)
        
        voucher = await self.get_voucher_by_id(str(result.inserted_id))
        return voucher, None

    async def get_voucher_by_id(self, voucher_id: str) -> Optional[Dict]:
        """Lấy voucher theo ID"""
        try:
            voucher = await self.collection.find_one({"_id": ObjectId(voucher_id)})
            if voucher:
                return await self._format_voucher(voucher)
        except:
            pass
        return None

    async def get_vouchers_by_shipping_unit(
        self, 
        shipping_unit_id: str, 
        page: int = 1, 
        limit: int = 10,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict:
        """Lấy danh sách voucher của đơn vị vận chuyển"""
        query = {"shipping_unit_id": ObjectId(shipping_unit_id)}
        
        if status:
            query["status"] = status
        
        if search:
            query["code"] = {"$regex": search, "$options": "i"}
        
        skip = (page - 1) * limit
        total = await self.collection.count_documents(query)
        
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        vouchers = []
        
        async for v in cursor:
            vouchers.append(await self._format_voucher(v))
        
        return {
            "data": vouchers,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if total > 0 else 1
            }
        }

    async def update_voucher(self, voucher_id: str, shipping_unit_id: str, update_data: dict) -> tuple:
        """Cập nhật voucher"""
        result = await self.collection.update_one(
            {
                "_id": ObjectId(voucher_id),
                "shipping_unit_id": ObjectId(shipping_unit_id)
            },
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            voucher = await self.get_voucher_by_id(voucher_id)
            return voucher, None
        return None, "Không tìm thấy voucher"

    async def update_status(self, voucher_id: str, shipping_unit_id: str, status: str) -> tuple:
        """Cập nhật trạng thái voucher"""
        result = await self.collection.update_one(
            {
                "_id": ObjectId(voucher_id),
                "shipping_unit_id": ObjectId(shipping_unit_id)
            },
            {"$set": {"status": status}}
        )
        
        if result.modified_count > 0:
            voucher = await self.get_voucher_by_id(voucher_id)
            return voucher, None
        return None, "Không tìm thấy voucher"

    async def delete_voucher(self, voucher_id: str, shipping_unit_id: str) -> bool:
        """Xóa voucher"""
        result = await self.collection.delete_one({
            "_id": ObjectId(voucher_id),
            "shipping_unit_id": ObjectId(shipping_unit_id)
        })
        return result.deleted_count > 0

    async def validate_voucher(
        self, 
        code: str, 
        order_total: float, 
        shipping_unit_id: str,
        user_id: str = None
    ) -> Dict:
        """Validate voucher vận chuyển"""
        try:
            voucher = await self.collection.find_one({
                "code": code.upper(),
                "shipping_unit_id": ObjectId(shipping_unit_id),
                "status": ShippingVoucherStatus.active.value
            })
            
            if not voucher:
                return {"error": "Voucher không hợp lệ"}
            
            # Kiểm tra ngày hết hạn
            end_date = voucher["end_date"]
            if end_date < datetime.utcnow():
                return {"error": f"Voucher đã hết hạn từ {end_date.strftime('%d/%m/%Y')}"}
            
            # Kiểm tra ngày bắt đầu
            start_date = voucher["start_date"]
            if start_date > datetime.utcnow():
                return {"error": f"Voucher có hiệu lực từ {start_date.strftime('%d/%m/%Y')}"}
            
            # Kiểm tra số lần sử dụng
            if voucher.get("usage_limit") and voucher["used_count"] >= voucher["usage_limit"]:
                return {"error": "Voucher đã hết lượt sử dụng"}
            
            # Kiểm tra đơn hàng tối thiểu
            min_order = voucher.get("min_order_value", 0)
            if order_total < min_order:
                return {"error": f"Đơn hàng phải từ {min_order:,.0f} VND để áp dụng voucher"}
            
            # Tính giảm giá
            discount = 0
            discount_type = voucher["discount_type"]
            discount_value = voucher["discount_value"]
            
            if discount_type == "percent":
                discount = order_total * discount_value / 100
                max_discount = voucher.get("max_discount")
                if max_discount:
                    discount = min(discount, max_discount)
            else:
                discount = min(discount_value, order_total)
            
            return {
                "valid": True,
                "discount": discount,
                "voucher": await self._format_voucher(voucher)
            }
            
        except Exception as e:
            print(f"Error validating shipping voucher: {e}")
            return {"error": str(e)}

    async def increase_usage(self, voucher_id: str) -> bool:
        """Tăng số lượng sử dụng voucher"""
        result = await self.collection.update_one(
            {"_id": ObjectId(voucher_id)},
            {"$inc": {"used_count": 1}}
        )
        return result.modified_count > 0

    async def get_stats(self, shipping_unit_id: str) -> Dict:
        """Lấy thống kê voucher của đơn vị vận chuyển"""
        pipeline = [
            {"$match": {"shipping_unit_id": ObjectId(shipping_unit_id)}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_used": {"$sum": "$used_count"}
            }}
        ]
        
        stats = await self.collection.aggregate(pipeline).to_list(length=None)
        
        result = {
            "total": 0,
            "active": 0,
            "inactive": 0,
            "expired": 0,
            "total_used": 0
        }
        
        for stat in stats:
            status = stat["_id"]
            result[status] = stat["count"]
            result["total"] += stat["count"]
            result["total_used"] += stat["total_used"]
        
        return result

    async def _format_voucher(self, voucher: dict) -> dict:
        """Format voucher response"""
        voucher["_id"] = str(voucher["_id"])
        voucher["shipping_unit_id"] = str(voucher["shipping_unit_id"])
        if voucher.get("shop_id"):
            voucher["shop_id"] = str(voucher["shop_id"])
        
        # Lấy tên đơn vị vận chuyển
        shipping_unit = await self.db["shipping_units"].find_one(
            {"_id": ObjectId(voucher["shipping_unit_id"])}
        )
        if shipping_unit:
            voucher["shipping_unit_name"] = shipping_unit.get("name", "")
        
        return voucher