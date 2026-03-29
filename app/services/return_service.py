# app/services/return_service.py
from bson import ObjectId
from datetime import datetime
from typing import List, Optional, Dict
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
        self.notification_service = None  # Sẽ inject sau

    def set_notification_service(self, notification_service):
        """Inject notification service"""
        self.notification_service = notification_service

    def generate_return_code(self):
        """Tạo mã yêu cầu đổi trả: RT + ngày tháng + 4 số ngẫu nhiên"""
        date_str = datetime.now().strftime("%y%m%d")
        random_num = ''.join(random.choices(string.digits, k=4))
        return f"RT{date_str}{random_num}"

        # app/services/return_service.py - Sửa lại phần create_return_request
    async def create_return_request(self, user_id: str, return_data: dict) -> tuple:
        """Tạo yêu cầu đổi trả mới"""
        try:
            print("\n" + "=" * 50)
            print("RETURN SERVICE - CREATE RETURN REQUEST")
            
            # Kiểm tra đơn hàng tồn tại
            try:
                order = await self.order_collection.find_one({
                    "_id": ObjectId(return_data["order_id"]),
                    "user_id": ObjectId(user_id)
                })
                print(f"Order found: {order is not None}")
                if order:
                    print(f"Order status: {order.get('status')}")
                    print(f"Order items count: {len(order.get('items', []))}")
                    # In ra các item trong order để debug
                    for idx, oi in enumerate(order.get('items', [])):
                        print(f"Order item {idx}: _id={oi.get('_id')}, product_id={oi.get('product_id')}, product_name={oi.get('product_name')}")
            except Exception as e:
                print(f"Error finding order: {str(e)}")
                return None, "Không tìm thấy đơn hàng"
            
            if not order:
                return None, "Không tìm thấy đơn hàng"
            
            # Kiểm tra đơn hàng đã giao chưa
            if order["status"] not in ["completed"]:
                return None, "Chỉ có thể đổi trả đơn hàng đã hoàn thành"
            
            # Kiểm tra thời gian đổi trả (trong vòng 7 ngày)
            created_at = order["created_at"]
            days_diff = (datetime.utcnow() - created_at).days
            if days_diff > 7:
                return None, "Chỉ có thể đổi trả trong vòng 7 ngày kể từ khi nhận hàng"
            
            # Kiểm tra đã có yêu cầu đổi trả trước đó chưa
            existing_return = await self.collection.find_one({
                "order_id": ObjectId(return_data["order_id"]),
                "status": {"$in": ["pending", "approved"]}
            })
            
            if existing_return:
                return None, "Đã có yêu cầu đổi trả đang được xử lý"
            
            # Tính tổng tiền hoàn trả
            total_refund = 0
            items_to_return = []
            
            print(f"\nProcessing {len(return_data['items'])} items from request:")
            for idx, item in enumerate(return_data["items"]):
                print(f"\nRequest item {idx}:")
                print(f"  order_item_id: {item['order_item_id']}")
                print(f"  product_name: {item['product_name']}")
                print(f"  quantity: {item['quantity']}")
                
                # Tìm item trong đơn hàng
                order_item = None
                for oi in order["items"]:
                    # So sánh với _id của order item
                    if str(oi.get("_id")) == item["order_item_id"]:
                        order_item = oi
                        print(f"  Found by _id match: {oi.get('_id')}")
                        break
                    # So sánh với product_id nếu không có _id
                    elif str(oi.get("product_id")) == item["product_id"]:
                        order_item = oi
                        print(f"  Found by product_id match: {oi.get('product_id')}")
                        break
                
                if not order_item:
                    print(f"  ERROR: Order item not found!")
                    print(f"  Available order items: {[oi.get('_id', 'no_id') for oi in order['items']]}")
                    return None, f"Không tìm thấy sản phẩm trong đơn hàng: {item['product_name']}"
                
                print(f"  Found order item: {order_item.get('product_name')} x {order_item.get('quantity')}")
                
                if item["quantity"] > order_item["quantity"]:
                    return None, f"Số lượng trả vượt quá số lượng đã mua: {item['product_name']}"
                
                # Lấy thông tin sản phẩm
                product = await self.product_collection.find_one(
                    {"_id": ObjectId(order_item["product_id"])}
                )
                
                item_total = order_item["price"] * item["quantity"]
                total_refund += item_total
                
                items_to_return.append({
                    "order_item_id": item["order_item_id"],
                    "product_id": str(order_item["product_id"]),
                    "product_name": product["name"] if product else item["product_name"],
                    "variant_id": str(order_item.get("variant_id")) if order_item.get("variant_id") else None,
                    "variant_name": order_item.get("variant_name"),
                    "quantity": item["quantity"],
                    "price": order_item["price"],
                    "reason": item["reason"],
                    "reason_note": item.get("reason_note", ""),
                    "images": item.get("images", [])
                })
            
            print(f"\nTotal refund: {total_refund}")
            
            # Tạo yêu cầu đổi trả
            return_request = {
                "return_code": self.generate_return_code(),
                "user_id": ObjectId(user_id),
                "order_id": ObjectId(return_data["order_id"]),
                "order_code": str(order["_id"])[-6:].upper(),
                "items": items_to_return,
                "total_refund": total_refund,
                "status": ReturnStatus.pending.value,
                "notes": return_data.get("notes", ""),
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
            
            print(f"Return request created: {return_request['return_code']}")
            print("=" * 50 + "\n")
            
            # Gửi thông báo cho shop
            if self.notification_service:
                shop_id = None
                for item in order["items"]:
                    shop_id = str(item["shop_id"])
                    break
                
                if shop_id:
                    await self.notification_service.create_notification(
                        user_id=shop_id,
                        type="system",
                        title="Yêu cầu đổi trả mới",
                        message=f"Đơn hàng #{return_request['order_code']} yêu cầu đổi trả sản phẩm",
                        reference_id=str(result.inserted_id)
                    )
            
            return return_request, None
            
        except Exception as e:
            print(f"Error in create_return_request: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, f"Lỗi server: {str(e)}"

    async def get_my_returns(self, user_id: str, page: int = 1, limit: int = 10) -> Dict:
        """Lấy danh sách yêu cầu đổi trả của user"""
        skip = (page - 1) * limit
        
        query = {"user_id": ObjectId(user_id)}
        
        # Đếm tổng số
        total = await self.collection.count_documents(query)
        
        # Lấy danh sách
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        returns = await cursor.to_list(length=limit)
        
        result = []
        for ret in returns:
            ret["_id"] = str(ret["_id"])
            ret["user_id"] = str(ret["user_id"])
            ret["order_id"] = str(ret["order_id"])
            result.append(ret)
        
        return {
            "data": result,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if total > 0 else 1
            }
        }

    async def get_return_detail(self, return_id: str, user_id: str = None) -> Optional[Dict]:
        """Xem chi tiết yêu cầu đổi trả"""
        query = {"_id": ObjectId(return_id)}
        
        if user_id:
            query["user_id"] = ObjectId(user_id)
        
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
            "total": order["total_amount"]
        } if order else None
        
        return ret

    async def get_shop_returns(
        self, 
        shop_id: str, 
        page: int = 1, 
        limit: int = 10,
        status: str = None,
        search: str = None
    ) -> Dict:
        """Lấy danh sách yêu cầu đổi trả của shop"""
        # Tìm tất cả đơn hàng của shop
        orders = await self.order_collection.find(
            {"items.shop_id": ObjectId(shop_id)}
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
                "total_pages": (total + limit - 1) // limit if total > 0 else 1
            }
        }

    async def update_return_status(
        self, 
        return_id: str, 
        shop_id: str,
        update_data: dict
    ) -> tuple:
        """Cập nhật trạng thái yêu cầu đổi trả"""
        # Kiểm tra yêu cầu tồn tại
        ret = await self.collection.find_one({"_id": ObjectId(return_id)})
        if not ret:
            return None, "Không tìm thấy yêu cầu"
        
        # Kiểm tra quyền shop
        order = await self.order_collection.find_one({"_id": ret["order_id"]})
        if not order:
            return None, "Không tìm thấy đơn hàng"
        
        # Kiểm tra shop có trong đơn hàng không
        shop_in_order = False
        for item in order["items"]:
            if str(item["shop_id"]) == shop_id:
                shop_in_order = True
                break
        
        if not shop_in_order:
            return None, "Không có quyền xử lý yêu cầu này"
        
        # Chuẩn bị dữ liệu cập nhật
        update_fields = {}
        
        if "status" in update_data:
            update_fields["status"] = update_data["status"]
            
            if update_data["status"] == ReturnStatus.approved.value:
                update_fields["approved_items"] = update_data.get("approved_items", [])
                update_fields["refund_amount"] = update_data.get("refund_amount", ret["total_refund"])
                update_fields["processed_at"] = datetime.utcnow()
                
                # Gửi thông báo cho user
                if self.notification_service:
                    await self.notification_service.create_notification(
                        user_id=str(ret["user_id"]),
                        type="system",
                        title="Yêu cầu đổi trả được chấp nhận",
                        message=f"Yêu cầu đổi trả #{ret['return_code']} đã được chấp nhận. Tiền sẽ được hoàn trong 3-5 ngày.",
                        reference_id=return_id
                    )
                
            elif update_data["status"] == ReturnStatus.rejected.value:
                update_fields["rejected_reason"] = update_data.get("rejected_reason")
                update_fields["processed_at"] = datetime.utcnow()
                
                # Gửi thông báo cho user
                if self.notification_service:
                    await self.notification_service.create_notification(
                        user_id=str(ret["user_id"]),
                        type="system",
                        title="Yêu cầu đổi trả bị từ chối",
                        message=f"Yêu cầu đổi trả #{ret['return_code']} bị từ chối. Lý do: {update_data.get('rejected_reason', 'Không rõ lý do')}",
                        reference_id=return_id
                    )
                
            elif update_data["status"] == ReturnStatus.completed.value:
                update_fields["completed_at"] = datetime.utcnow()
                
                # Hoàn kho cho sản phẩm
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
                
                # Gửi thông báo hoàn tất
                if self.notification_service:
                    await self.notification_service.create_notification(
                        user_id=str(ret["user_id"]),
                        type="system",
                        title="Đã hoàn trả thành công",
                        message=f"Yêu cầu đổi trả #{ret['return_code']} đã được hoàn tất. Cảm ơn bạn đã đồng hành!",
                        reference_id=return_id
                    )
        
        if "admin_note" in update_data:
            update_fields["admin_note"] = update_data["admin_note"]
        
        if update_fields:
            await self.collection.update_one(
                {"_id": ObjectId(return_id)},
                {"$set": update_fields}
            )
        
        return await self.get_return_detail(return_id), None

    async def get_return_stats(self, shop_id: str = None, user_id: str = None) -> Dict:
        """Lấy thống kê đổi trả"""
        if shop_id:
            # Thống kê cho shop
            orders = await self.order_collection.find(
                {"items.shop_id": ObjectId(shop_id)}
            ).to_list(length=None)
            order_ids = [o["_id"] for o in orders]
            query = {"order_id": {"$in": order_ids}}
        elif user_id:
            # Thống kê cho user
            query = {"user_id": ObjectId(user_id)}
        else:
            query = {}
        
        # Thống kê theo trạng thái
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_refund": {"$sum": "$total_refund"}
            }}
        ]
        
        status_stats = await self.collection.aggregate(pipeline).to_list(length=None)
        
        stats = {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "completed": 0,
            "cancelled": 0,
            "total": 0,
            "total_refund": 0
        }
        
        for stat in status_stats:
            stats[stat["_id"]] = stat["count"]
            stats["total"] += stat["count"]
            if stat["_id"] in ["approved", "completed"]:
                stats["total_refund"] += stat["total_refund"]
        
        return stats