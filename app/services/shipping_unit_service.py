# app/services/shipping_unit_service.py
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
from app.models.shipping_unit_model import ShippingUnitStatus

class ShippingUnitService:
    def __init__(self, db):
        self.collection = db["shipping_units"]
        self.db = db
        self.notification_service = None

    async def _get_notification_service(self):
        if not self.notification_service:
            from app.services.notification_service import NotificationService
            self.notification_service = NotificationService(self.db)
        return self.notification_service

    async def create_shipping_unit(self, data: dict, shop_id: str):
        """Tạo đơn vị vận chuyển mới cho shop"""
        # Kiểm tra code trùng trong shop
        existing = await self.collection.find_one({
            "code": data["code"],
            "shop_id": ObjectId(shop_id)
        })
        if existing:
            return None, "Mã đơn vị vận chuyển đã tồn tại trong shop của bạn"
        
        # Tạo đơn vị vận chuyển mới
        shipping_unit = {
            **data,
            "shop_id": ObjectId(shop_id),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "total_orders": 0,
            "total_revenue": 0
        }
        
        result = await self.collection.insert_one(shipping_unit)
        new_unit = await self.get_shipping_unit_by_id(str(result.inserted_id), shop_id)
        
        # Tạo thông báo cho shop owner
        await self._notify_shop_new_shipping_unit(new_unit, shop_id)
        
        return new_unit, None

    async def get_shipping_unit_by_id(self, unit_id: str, shop_id: str = None):
        """Lấy thông tin đơn vị vận chuyển theo ID"""
        try:
            query = {"_id": ObjectId(unit_id)}
            if shop_id:
                query["shop_id"] = ObjectId(shop_id)
            
            unit = await self.collection.find_one(query)
            if unit:
                unit["_id"] = str(unit["_id"])
                unit["shop_id"] = str(unit["shop_id"])
                # Thêm trường id để tương thích
                unit["id"] = unit["_id"]
                return unit
        except:
            pass
        return None

    async def get_shipping_unit_by_code(self, code: str, shop_id: str):
        """Lấy thông tin đơn vị vận chuyển theo mã và shop"""
        unit = await self.collection.find_one({
            "code": code,
            "shop_id": ObjectId(shop_id)
        })
        if unit:
            unit["_id"] = str(unit["_id"])
            unit["shop_id"] = str(unit["shop_id"])
            unit["id"] = unit["_id"]
            return unit
        return None

    async def list_shipping_units_by_shop(self, shop_id: str, skip: int = 0, limit: int = 20, status: Optional[str] = None):
        """Lấy danh sách đơn vị vận chuyển của shop"""
        query = {"shop_id": ObjectId(shop_id)}
        if status:
            query["status"] = status
            
        cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        units = []
        
        async for unit in cursor:
            unit["_id"] = str(unit["_id"])
            unit["shop_id"] = str(unit["shop_id"])
            unit["id"] = unit["_id"]
            units.append(unit)
            
        total = await self.collection.count_documents(query)
        
        return {
            "data": units,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if total > 0 else 1
            }
        }

    async def update_shipping_unit(self, unit_id: str, update_data: dict, shop_id: str):
        """Cập nhật thông tin đơn vị vận chuyển của shop"""
        # Kiểm tra code trùng nếu đổi code
        if "code" in update_data:
            existing = await self.collection.find_one({
                "code": update_data["code"],
                "shop_id": ObjectId(shop_id),
                "_id": {"$ne": ObjectId(unit_id)}
            })
            if existing:
                return None, "Mã đơn vị vận chuyển đã tồn tại trong shop"
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {
                "_id": ObjectId(unit_id),
                "shop_id": ObjectId(shop_id)
            },
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            updated_unit = await self.get_shipping_unit_by_id(unit_id, shop_id)
            # Tạo thông báo khi cập nhật
            await self._notify_shop_update_shipping_unit(updated_unit, shop_id)
            return updated_unit, None
        return None, "Không tìm thấy đơn vị vận chuyển"

    async def delete_shipping_unit(self, unit_id: str, shop_id: str):
        """Xóa đơn vị vận chuyển của shop"""
        # Kiểm tra có đơn hàng nào đang sử dụng không
        orders_count = await self.db["orders"].count_documents({
            "shipping_unit_id": unit_id,
            "shop_id": ObjectId(shop_id),
            "status": {"$in": ["pending", "paid", "shipped"]}
        })
        
        if orders_count > 0:
            return False, f"Có {orders_count} đơn hàng đang sử dụng đơn vị vận chuyển này. Không thể xóa."
        
        result = await self.collection.delete_one({
            "_id": ObjectId(unit_id),
            "shop_id": ObjectId(shop_id)
        })
        return result.deleted_count > 0, None

    async def update_status(self, unit_id: str, status: ShippingUnitStatus, shop_id: str):
        """Cập nhật trạng thái đơn vị vận chuyển"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.update_one(
            {
                "_id": ObjectId(unit_id),
                "shop_id": ObjectId(shop_id)
            },
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            unit = await self.get_shipping_unit_by_id(unit_id, shop_id)
            await self._notify_shop_status_change(unit, shop_id)
            return unit, None
        return None, "Không tìm thấy đơn vị vận chuyển"

    async def calculate_shipping_fee(self, unit_id: str, order_total: float, province: str, shop_id: str):
        """Tính phí vận chuyển cho đơn hàng của shop"""
        unit = await self.get_shipping_unit_by_id(unit_id, shop_id)
        if not unit or unit["status"] != "active":
            return None, "Đơn vị vận chuyển không khả dụng"
            
        # Kiểm tra hỗ trợ tỉnh/thành
        if unit.get("supported_provinces") and province not in unit["supported_provinces"]:
            return None, "Đơn vị vận chuyển không hỗ trợ tỉnh/thành này"
            
        # Kiểm tra miễn phí ship
        if unit.get("free_shipping_threshold") and order_total >= unit["free_shipping_threshold"]:
            return 0, None
            
        return unit.get("shipping_fee_base", 0), None

    async def get_shop_shipping_stats(self, shop_id: str):
        """Lấy thống kê vận chuyển cho shop"""
        try:
            # Đơn giản hóa pipeline
            pipeline = [
                {"$match": {"shop_id": ObjectId(shop_id)}},
                {"$lookup": {
                    "from": "orders",
                    "localField": "_id",
                    "foreignField": "shipping_unit_id",
                    "as": "orders"
                }},
                {"$project": {
                    "unit_id": {"$toString": "$_id"},
                    "unit_name": "$name",
                    "unit_code": "$code",
                    "total_orders": {"$size": "$orders"},
                    "total_revenue": {"$sum": "$orders.total_amount"},
                    "success_orders": {
                        "$size": {
                            "$filter": {
                                "input": "$orders",
                                "as": "order",
                                "cond": {"$eq": ["$$order.status", "completed"]}
                            }
                        }
                    }
                }}
            ]
            
            stats = []
            async for unit in self.collection.aggregate(pipeline):
                # Chuyển đổi tất cả các giá trị sang kiểu Python cơ bản
                total = unit.get("total_orders", 0)
                success = unit.get("success_orders", 0)
                success_rate = (success / total * 100) if total > 0 else 0
                
                stat = {
                    "unit_id": str(unit.get("unit_id", "")),
                    "unit_name": str(unit.get("unit_name", "")),
                    "unit_code": str(unit.get("unit_code", "")),
                    "total_orders": int(total),
                    "total_revenue": float(unit.get("total_revenue", 0)),
                    "success_rate": float(success_rate),
                    "avg_delivery_days": 0.0
                }
                stats.append(stat)
            
            return stats
        except Exception as e:
            print(f"Error in get_shop_shipping_stats: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _notify_shop_new_shipping_unit(self, unit: dict, shop_id: str):
        """Thông báo cho shop khi tạo đơn vị vận chuyển mới"""
        if not unit:
            return
            
        notification_service = await self._get_notification_service()
        
        # Lấy owner của shop
        shop = await self.db["shops"].find_one({"_id": ObjectId(shop_id)})
        if shop and shop.get("owner_id"):
            reference_id = unit.get("_id") or unit.get("id")
            await notification_service.create_notification(
                user_id=str(shop["owner_id"]),
                type="shipping_unit",
                title="Đơn vị vận chuyển mới",
                message=f"Đã thêm đơn vị vận chuyển {unit.get('name', '')} vào hệ thống",
                reference_id=reference_id
            )

    async def _notify_shop_update_shipping_unit(self, unit: dict, shop_id: str):
        """Thông báo cho shop khi cập nhật đơn vị vận chuyển"""
        if not unit:
            return
            
        notification_service = await self._get_notification_service()
        
        shop = await self.db["shops"].find_one({"_id": ObjectId(shop_id)})
        if shop and shop.get("owner_id"):
            reference_id = unit.get("_id") or unit.get("id")
            await notification_service.create_notification(
                user_id=str(shop["owner_id"]),
                type="shipping_unit",
                title="Cập nhật đơn vị vận chuyển",
                message=f"Đã cập nhật thông tin đơn vị vận chuyển {unit.get('name', '')}",
                reference_id=reference_id
            )

    async def _notify_shop_status_change(self, unit: dict, shop_id: str):
        """Thông báo khi thay đổi trạng thái đơn vị vận chuyển"""
        if not unit:
            return
            
        notification_service = await self._get_notification_service()
        
        status_messages = {
            "active": "đã được kích hoạt",
            "inactive": "đã bị vô hiệu hóa",
            "suspended": "đã bị tạm ngưng"
        }
        
        shop = await self.db["shops"].find_one({"_id": ObjectId(shop_id)})
        if shop and shop.get("owner_id"):
            reference_id = unit.get("_id") or unit.get("id")
            await notification_service.create_notification(
                user_id=str(shop["owner_id"]),
                type="shipping_unit",
                title="Thay đổi trạng thái",
                message=f"Đơn vị vận chuyển {unit.get('name', '')} {status_messages.get(unit.get('status', ''), 'đã thay đổi trạng thái')}",
                reference_id=reference_id
            )