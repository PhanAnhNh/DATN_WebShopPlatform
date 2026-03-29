from bson import ObjectId
from datetime import datetime
from app.models.orders_model import OrderStatus
from app.services.notification_service import NotificationService
from app.services.shipping_unit_service import ShippingUnitService

class OrderService:

    def __init__(self, db):
        self.db = db
        self.collection = db["orders"]
        self.product_collection = db["products"]
        self.shop_collection = db["shops"]
        self.cart_collection = db["carts"]
        self.variant_collection = db["product_variants"]
        self.notification_service = NotificationService(db)
        self.shipping_unit_service = ShippingUnitService(db)

    async def create_order(self, user_id: str, order_data: dict):
        total_price = 0
        items_to_save = []
        
        # Validate each item
        for item in order_data["items"]:
            if item.get("variant_id"):
                variant = await self.variant_collection.find_one({"_id": ObjectId(item["variant_id"])})
                if not variant or variant["stock"] < item["quantity"]:
                    raise Exception(f"Sản phẩm {item.get('variant_name')} không đủ hàng")
                
                price = variant["price"]
                await self.variant_collection.update_one(
                    {"_id": variant["_id"]}, 
                    {"$inc": {"stock": -item["quantity"]}}
                )
            else:
                product = await self.product_collection.find_one({"_id": ObjectId(item["product_id"])})
                if not product or product.get("stock", 0) < item["quantity"]:
                    raise Exception("Sản phẩm không đủ hàng")
                
                price = product.get("price", 0)
                await self.product_collection.update_one(
                    {"_id": product["_id"]}, 
                    {"$inc": {"stock": -item["quantity"]}}
                )
            
            total_price += price * item["quantity"]
            items_to_save.append({
                "product_id": ObjectId(item["product_id"]),
                "variant_id": ObjectId(item["variant_id"]) if item.get("variant_id") else None,
                "shop_id": ObjectId(item["shop_id"]),
                "quantity": item["quantity"],
                "price": price,
                "variant_name": item.get("variant_name", "")
            })
        
        # Format shipping address
        shipping_addr = order_data["shipping_address"]
        formatted_address = shipping_addr.get("full_address") or f"{shipping_addr['street']}, {shipping_addr['ward']}, {shipping_addr['district']}, {shipping_addr['city']}, {shipping_addr['country']}"
        
        # Lấy thông tin shipping unit nếu có
        shipping_unit_info = None
        if order_data.get("shipping_unit_id"):
            shipping_unit = await self.shipping_unit_service.get_shipping_unit_by_id(
                order_data["shipping_unit_id"],
                None  # Không cần shop_id khi lấy thông tin cơ bản
            )
            if shipping_unit:
                shipping_unit_info = {
                    "id": shipping_unit["id"],
                    "name": shipping_unit["name"],
                    "code": shipping_unit["code"],
                    "shipping_fee": order_data["shipping_fee"],
                    "estimated_delivery_days": shipping_unit["estimated_delivery_days"]
                }
        
        # Create order
        order = {
            "user_id": ObjectId(user_id),
            "items": items_to_save,
            "total_amount": order_data["total_amount"],
            "subtotal": order_data["subtotal"],
            "discount": order_data["discount"],
            "shipping_fee": order_data["shipping_fee"],
            "shipping_address": formatted_address,
            "shipping_address_details": shipping_addr,
            "note": order_data.get("note", ""),
            "payment_method": order_data["payment_method"],
            "payment_status": "unpaid",
            "status": OrderStatus.pending.value,
            "created_at": datetime.utcnow()
        }
        
        # Thêm shipping unit info nếu có
        if shipping_unit_info:
            order["shipping_unit"] = shipping_unit_info
            order["shipping_unit_id"] = ObjectId(order_data["shipping_unit_id"])
        
        # Add voucher if present
        if order_data.get("voucher"):
            order["voucher"] = {
                "id": ObjectId(order_data["voucher"]["id"]),
                "code": order_data["voucher"]["code"],
                "discount": order_data["voucher"]["discount"]
            }
        
        result = await self.collection.insert_one(order)
        
        # Clear cart
        await self.cart_collection.delete_one({"user_id": ObjectId(user_id)})
        
        order_id = str(result.inserted_id)
        
        # ========== TẠO THÔNG BÁO ==========
        # 1. Thông báo cho người đặt hàng
        await self.notification_service.create_notification(
            user_id=user_id,
            type="order",
            title="Đặt hàng thành công",
            message=f"Đơn hàng #{order_id[-8:].upper()} đã được đặt thành công",
            reference_id=order_id
        )
        
        # 2. Thông báo cho các shop
        shop_ids = set()
        for item in order_data["items"]:
            shop_ids.add(item["shop_id"])
        
        for shop_id in shop_ids:
            await self.notification_service.create_notification(
                user_id=shop_id,
                type="order",
                title="Đơn hàng mới",
                message=f"Có đơn hàng mới #{order_id[-8:].upper()} cần xử lý",
                reference_id=order_id
            )
        
        # Convert ObjectId to string before returning
        order["_id"] = order_id
        order["user_id"] = str(order["user_id"])
        if order.get("voucher") and order["voucher"].get("id"):
            order["voucher"]["id"] = str(order["voucher"]["id"])
        if order.get("shipping_unit_id"):
            order["shipping_unit_id"] = str(order["shipping_unit_id"])
        
        for item in order["items"]:
            item["product_id"] = str(item["product_id"])
            item["shop_id"] = str(item["shop_id"])
            if item.get("variant_id"):
                item["variant_id"] = str(item["variant_id"])
        
        return order

    async def get_user_orders(self, user_id: str):
        cursor = self.collection.find({
            "user_id": ObjectId(user_id)
        }).sort("created_at", -1)

        orders = []

        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["user_id"] = str(doc["user_id"])

            for item in doc.get("items", []):
                item["product_id"] = str(item["product_id"])
                item["shop_id"] = str(item["shop_id"])
                if item.get("variant_id"):
                    item["variant_id"] = str(item["variant_id"])

            orders.append(doc)

        return orders

    # app/services/order_service.py
    async def get_order(self, order_id: str):
        try:
            order = await self.collection.find_one({
                "_id": ObjectId(order_id)
            })
        except:
            return None

        if not order:
            return None

        # Tạo dict mới để tránh lỗi ObjectId
        result = {
            "_id": str(order["_id"]),
            "user_id": str(order["user_id"]),
            "total_amount": order.get("total_amount", 0),
            "total_price": order.get("total_amount", 0),
            "subtotal": order.get("subtotal", 0),
            "discount": order.get("discount", 0),
            "shipping_fee": order.get("shipping_fee", 0),
            "status": order.get("status", "pending"),
            "payment_status": order.get("payment_status", "unpaid"),
            "payment_method": order.get("payment_method", "cod"),
            "shipping_address": order.get("shipping_address", ""),
            "shipping_address_details": order.get("shipping_address_details", {}),
            "note": order.get("note", ""),
            "created_at": order.get("created_at")
        }
        
        # Xử lý items
        items = []
        for idx, item in enumerate(order.get("items", [])):
            items.append({
                "_id": f"{result['_id']}_item_{idx}",
                "product_id": str(item.get("product_id")),
                "shop_id": str(item.get("shop_id")),
                "quantity": item.get("quantity", 0),
                "price": item.get("price", 0),
                "variant_id": str(item.get("variant_id")) if item.get("variant_id") else None,
                "variant_name": item.get("variant_name", "")
            })
        
        result["items"] = items
        
        # Xử lý voucher
        if order.get("voucher"):
            voucher = order["voucher"]
            result["voucher"] = {
                "id": str(voucher.get("id")) if voucher.get("id") else None,
                "code": voucher.get("code", ""),
                "discount": voucher.get("discount", 0)
            }
        
        # Xử lý shipping unit
        if order.get("shipping_unit"):
            result["shipping_unit"] = order.get("shipping_unit")
        
        if order.get("shipping_unit_id"):
            result["shipping_unit_id"] = str(order["shipping_unit_id"])
        
        return result

    async def update_order_status(self, order_id: str, status: OrderStatus):
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": status.value}}
        )
        
        # Nếu chuyển sang trạng thái shipped, có thể gửi thông báo
        if status == OrderStatus.shipped:
            order = await self.get_order(order_id)
            if order:
                # Thông báo cho khách hàng
                await self.notification_service.create_notification(
                    user_id=order["user_id"],
                    type="order",
                    title="Đơn hàng đã giao",
                    message=f"Đơn hàng #{order_id[-8:].upper()} đã được giao cho đơn vị vận chuyển",
                    reference_id=order_id
                )
        
        return await self.get_order(order_id)
    
    async def update_payment_status(self, order_id: str, status: str):
        """Cập nhật khi khách đã trả tiền (gọi từ Webhook hoặc Admin)"""
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"payment_status": status}}
        )
        return await self.get_order(order_id)

    async def cancel_order(self, order_id: str, user_id: str):
        try:
            order = await self.collection.find_one({
                "_id": ObjectId(order_id),
                "user_id": ObjectId(user_id)
            })
        except:
            raise Exception("Không tìm thấy đơn hàng")

        if not order:
            raise Exception("Không tìm thấy đơn hàng")
        
        if order["status"] not in [OrderStatus.pending.value, OrderStatus.paid.value]:
            raise Exception("Không thể hủy đơn hàng ở trạng thái này")

        # 1. Hoàn lại kho (Stock)
        for item in order.get("items", []):
            if item.get("variant_id"):
                await self.db["product_variants"].update_one(
                    {"_id": ObjectId(item["variant_id"])},
                    {"$inc": {"stock": item["quantity"]}}
                )
            else:
                await self.db["products"].update_one(
                    {"_id": ObjectId(item["product_id"])},
                    {"$inc": {"stock": item["quantity"]}}
                )
            
            # 2. Trừ lại doanh thu dự kiến của Shop
            await self.shop_collection.update_one(
                {"_id": ObjectId(item["shop_id"])},
                {"$inc": {
                    "total_revenue": -(item["price"] * item["quantity"]),
                    "total_orders": -1
                }}
            )

        # 3. Cập nhật trạng thái đơn hàng
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": OrderStatus.cancelled.value, "cancelled_at": datetime.utcnow()}}
        )

        return {"status": "success", "message": "Đơn hàng đã được hủy và hoàn kho"}