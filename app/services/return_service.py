# app/services/return_service.py
from bson import ObjectId
from datetime import datetime
from app.models.return_model import ReturnStatus, ReturnReason
import random
import string

class ReturnService:
    def __init__(self, db):
        self.db = db
        self.collection = db["returns"]
        self.order_collection = db["orders"]
        self.product_collection = db["products"]
        self.variant_collection = db["product_variants"]
        self.user_collection = db["users"]

    def generate_return_code(self):
        """Tạo mã yêu cầu đổi trả: RT + ngày tháng + 4 số ngẫu nhiên"""
        date_str = datetime.now().strftime("%y%m%d")
        random_num = ''.join(random.choices(string.digits, k=4))
        return f"RT{date_str}{random_num}"

    async def create_return_request(self, user_id: str, return_data: dict):
        """Tạo yêu cầu đổi trả mới"""
        # Kiểm tra đơn hàng tồn tại
        order = await self.order_collection.find_one({
            "_id": ObjectId(return_data["order_id"]),
            "user_id": ObjectId(user_id)
        })
        
        if not order:
            return None, "Không tìm thấy đơn hàng"
        
        # Kiểm tra đơn hàng đã giao chưa
        if order["status"] not in ["completed"]:
            return None, "Chỉ có thể đổi trả đơn hàng đã hoàn thành"
        
        # Tính tổng tiền hoàn trả
        total_refund = 0
        items_to_return = []
        
        for item in return_data["items"]:
            # Tìm item trong đơn hàng
            order_item = next(
                (i for i in order["items"] if str(i["_id"]) == item["order_item_id"]),
                None
            )
            
            if not order_item:
                return None, f"Không tìm thấy sản phẩm trong đơn hàng"
            
            if item["quantity"] > order_item["quantity"]:
                return None, f"Số lượng trả vượt quá số lượng đã mua"
            
            # Lấy thông tin sản phẩm
            product = await self.product_collection.find_one(
                {"_id": order_item["product_id"]}
            )
            
            item_total = order_item["price"] * item["quantity"]
            total_refund += item_total
            
            items_to_return.append({
                "order_item_id": item["order_item_id"],
                "product_id": str(order_item["product_id"]),
                "product_name": product["name"] if product else "Sản phẩm",
                "variant_id": str(order_item.get("variant_id")) if order_item.get("variant_id") else None,
                "variant_name": order_item.get("variant_name"),
                "quantity": item["quantity"],
                "price": order_item["price"],
                "reason": item["reason"],
                "reason_note": item.get("reason_note"),
                "images": item.get("images", [])
            })
        
        # Tạo yêu cầu đổi trả
        return_request = {
            "return_code": self.generate_return_code(),
            "user_id": ObjectId(user_id),
            "order_id": ObjectId(return_data["order_id"]),
            "order_code": str(order["_id"])[-6:].upper(),
            "items": items_to_return,
            "total_refund": total_refund,
            "status": ReturnStatus.pending.value,
            "notes": return_data.get("notes"),
            "bank_name": return_data.get("bank_name"),
            "bank_account": return_data.get("bank_account"),
            "bank_holder": return_data.get("bank_holder"),
            "created_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(return_request)
        
        # Lấy thông tin user
        user = await self.user_collection.find_one({"_id": ObjectId(user_id)})
        
        return_request["_id"] = str(result.inserted_id)
        return_request["user_id"] = str(return_request["user_id"])
        return_request["order_id"] = str(return_request["order_id"])
        return_request["user_name"] = user.get("full_name") if user else ""
        return_request["user_phone"] = user.get("phone") if user else ""
        
        return return_request, None

    async def get_shop_returns(
        self, 
        shop_id: str, 
        page: int = 1, 
        limit: int = 10,
        status: str = None,
        search: str = None
    ):
        """Lấy danh sách yêu cầu đổi trả của shop"""
        shop_id = ObjectId(shop_id)
        
        # Tìm tất cả đơn hàng của shop
        orders = await self.order_collection.find(
            {"items.shop_id": shop_id}
        ).to_list(length=None)
        
        order_ids = [o["_id"] for o in orders]
        
        # Build query
        query = {"order_id": {"$in": order_ids}}
        
        if status:
            query["status"] = status
        
        if search:
            # Tìm theo mã yêu cầu hoặc tên khách hàng
            users = await self.user_collection.find({
                "$or": [
                    {"full_name": {"$regex": search, "$options": "i"}},
                    {"username": {"$regex": search, "$options": "i"}},
                    {"phone": {"$regex": search, "$options": "i"}}
                ]
            }).to_list(length=None)
            
            user_ids = [u["_id"] for u in users]
            
            query["$or"] = [
                {"return_code": {"$regex": search, "$options": "i"}},
                {"user_id": {"$in": user_ids}}
            ]
        
        # Tính skip
        skip = (page - 1) * limit
        
        # Đếm tổng số
        total = await self.collection.count_documents(query)
        
        # Lấy danh sách
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        returns = await cursor.to_list(length=limit)
        
        # Lấy thông tin user cho mỗi yêu cầu
        result = []
        for ret in returns:
            user = await self.user_collection.find_one({"_id": ret["user_id"]})
            
            ret["_id"] = str(ret["_id"])
            ret["user_id"] = str(ret["user_id"])
            ret["order_id"] = str(ret["order_id"])
            ret["user_name"] = user.get("full_name") if user else ""
            ret["user_phone"] = user.get("phone") if user else ""
            
            result.append(ret)
        
        return {
            "data": result,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit
            }
        }

    async def get_return_detail(self, return_id: str, shop_id: str = None):
        """Xem chi tiết yêu cầu đổi trả"""
        query = {"_id": ObjectId(return_id)}
        
        if shop_id:
            # Kiểm tra quyền shop
            ret = await self.collection.find_one(query)
            if not ret:
                return None
            
            order = await self.order_collection.find_one({"_id": ret["order_id"]})
            if not order or str(order.get("shop_id")) != shop_id:
                return None
        
        ret = await self.collection.find_one(query)
        
        if not ret:
            return None
        
        # Lấy thông tin user
        user = await self.user_collection.find_one({"_id": ret["user_id"]})
        
        # Lấy thông tin đơn hàng
        order = await self.order_collection.find_one({"_id": ret["order_id"]})
        
        ret["_id"] = str(ret["_id"])
        ret["user_id"] = str(ret["user_id"])
        ret["order_id"] = str(ret["order_id"])
        ret["user_name"] = user.get("full_name") if user else ""
        ret["user_phone"] = user.get("phone") if user else ""
        ret["user_email"] = user.get("email") if user else ""
        ret["order_info"] = {
            "order_code": str(order["_id"])[-6:].upper(),
            "created_at": order["created_at"],
            "total": order["total_price"]
        } if order else None
        
        return ret

    async def update_return_status(
        self, 
        return_id: str, 
        shop_id: str,
        update_data: dict
    ):
        """Cập nhật trạng thái yêu cầu đổi trả"""
        # Kiểm tra yêu cầu tồn tại
        ret = await self.collection.find_one({"_id": ObjectId(return_id)})
        if not ret:
            return None, "Không tìm thấy yêu cầu"
        
        # Kiểm tra quyền shop
        order = await self.order_collection.find_one({"_id": ret["order_id"]})
        if not order or str(order.get("shop_id")) != shop_id:
            return None, "Không có quyền xử lý yêu cầu này"
        
        # Chuẩn bị dữ liệu cập nhật
        update_fields = {}
        
        if "status" in update_data:
            update_fields["status"] = update_data["status"]
            
            if update_data["status"] == ReturnStatus.approved.value:
                update_fields["approved_items"] = update_data.get("approved_items", [])
                update_fields["refund_amount"] = update_data.get("refund_amount")
                update_fields["processed_at"] = datetime.utcnow()
                
                # TODO: Xử lý hoàn tiền nếu cần
                
            elif update_data["status"] == ReturnStatus.rejected.value:
                update_fields["rejected_reason"] = update_data.get("rejected_reason")
                update_fields["processed_at"] = datetime.utcnow()
                
            elif update_data["status"] == ReturnStatus.completed.value:
                update_fields["completed_at"] = datetime.utcnow()
                
                # Hoàn kho
                for item in ret["items"]:
                    if item.get("variant_id"):
                        await self.variant_collection.update_one(
                            {"_id": ObjectId(item["variant_id"])},
                            {"$inc": {"stock": item["quantity"]}}
                        )
                    else:
                        await self.product_collection.update_one(
                            {"_id": ObjectId(item["product_id"])},
                            {"$inc": {"stock": item["quantity"]}}
                        )
        
        if "admin_note" in update_data:
            update_fields["admin_note"] = update_data["admin_note"]
        
        if update_fields:
            await self.collection.update_one(
                {"_id": ObjectId(return_id)},
                {"$set": update_fields}
            )
        
        return await self.get_return_detail(return_id), None

    async def get_return_stats(self, shop_id: str):
        """Lấy thống kê đổi trả cho dashboard"""
        shop_id = ObjectId(shop_id)
        
        # Tìm tất cả đơn hàng của shop
        orders = await self.order_collection.find(
            {"items.shop_id": shop_id}
        ).to_list(length=None)
        
        order_ids = [o["_id"] for o in orders]
        
        # Thống kê theo trạng thái
        pipeline = [
            {"$match": {"order_id": {"$in": order_ids}}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        status_stats = await self.collection.aggregate(pipeline).to_list(length=None)
        
        stats = {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "completed": 0,
            "cancelled": 0,
            "total": 0
        }
        
        for stat in status_stats:
            stats[stat["_id"]] = stat["count"]
            stats["total"] += stat["count"]
        
        # Tổng tiền hoàn trả
        pipeline_refund = [
            {"$match": {
                "order_id": {"$in": order_ids},
                "status": {"$in": ["approved", "completed"]}
            }},
            {"$group": {
                "_id": None,
                "total_refund": {"$sum": "$total_refund"}
            }}
        ]
        
        refund_result = await self.collection.aggregate(pipeline_refund).to_list(length=None)
        stats["total_refund"] = refund_result[0]["total_refund"] if refund_result else 0
        
        return stats