from bson import ObjectId
from datetime import datetime

from app.models.orders_model import OrderStatus  # THIẾU DÒNG NÀY


class OrderService:

    def __init__(self, db):
        self.db = db
        self.collection = db["orders"]
        self.product_collection = db["products"]
        self.shop_collection = db["shops"]
        self.cart_collection = db["carts"]
        self.variant_collection = db["product_variants"]

    async def create_order(self, user_id: str, order_data: dict):
        total_price = 0
        items_to_save = []

        for item in order_data["items"]:
            # 1. Check kho và lấy giá
            if item.get("variant_id"):
                variant = await self.variant_collection.find_one({"_id": ObjectId(item["variant_id"])})
                if not variant or variant["stock"] < item["quantity"]:
                    raise Exception(f"Sản phẩm {item.get('variant_name')} không đủ hàng")
                
                price = variant["price"]
                # Trừ kho Variant
                await self.variant_collection.update_one(
                    {"_id": variant["_id"]}, 
                    {"$inc": {"stock": -item["quantity"]}}
                )
            else:
                product = await self.product_collection.find_one({"_id": ObjectId(item["product_id"])})
                if not product or product.get("stock", 0) < item["quantity"]:
                    raise Exception("Sản phẩm không đủ hàng")
                
                price = product.get("price", 0)
                # Trừ kho Product
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

        # 2. Tạo object đơn hàng đơn giản
        order = {
            "user_id": ObjectId(user_id),
            "items": items_to_save,
            "total_price": total_price,
            "shipping_address": order_data["shipping_address"],
            "status": OrderStatus.pending.value,  # SỬA: dùng .value
            "created_at": datetime.utcnow()
        }

        result = await self.collection.insert_one(order)
        
        # 3. Xóa giỏ hàng
        await self.cart_collection.delete_one({"user_id": ObjectId(user_id)})

        # SỬA: Convert ObjectId sang string trước khi return
        order["_id"] = str(result.inserted_id)
        order["user_id"] = str(order["user_id"])
        for item in order["items"]:
            item["product_id"] = str(item["product_id"])
            item["shop_id"] = str(item["shop_id"])
            if item["variant_id"]:
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

            for item in doc["items"]:
                item["product_id"] = str(item["product_id"])
                item["shop_id"] = str(item["shop_id"])
                if item.get("variant_id"):
                    item["variant_id"] = str(item["variant_id"])

            orders.append(doc)

        return orders

    async def get_order(self, order_id: str):
        order = await self.collection.find_one({
            "_id": ObjectId(order_id)
        })

        if not order:
            return None

        order["_id"] = str(order["_id"])
        order["user_id"] = str(order["user_id"])

        for item in order["items"]:
            item["product_id"] = str(item["product_id"])
            item["shop_id"] = str(item["shop_id"])
            if item.get("variant_id"):
                item["variant_id"] = str(item["variant_id"])

        return order

    async def update_order_status(self, order_id: str, status: OrderStatus):
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": status.value}}  # SỬA: dùng .value
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
        order = await self.collection.find_one({
            "_id": ObjectId(order_id),
            "user_id": ObjectId(user_id)
        })

        if not order:
            raise Exception("Không tìm thấy đơn hàng")
        
        if order["status"] not in [OrderStatus.pending.value, OrderStatus.paid.value]:  # SỬA
            raise Exception("Không thể hủy đơn hàng ở trạng thái này")

        # 1. Hoàn lại kho (Stock)
        for item in order["items"]:
            if item.get("variant_id"):
                await self.db["product_variants"].update_one(
                    {"_id": ObjectId(item["variant_id"])},  # SỬA: convert sang ObjectId
                    {"$inc": {"stock": item["quantity"]}}
                )
            else:
                await self.db["products"].update_one(
                    {"_id": ObjectId(item["product_id"])},  # SỬA: convert sang ObjectId
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
            {"$set": {"status": OrderStatus.cancelled.value, "cancelled_at": datetime.utcnow()}}  # SỬA
        )

        return {"status": "success", "message": "Đơn hàng đã được hủy và hoàn kho"}