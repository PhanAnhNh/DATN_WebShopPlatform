from typing import Optional
from bson import ObjectId

class CartService:

    def __init__(self, db):
        self.collection = db["carts"]

    async def add_to_cart(self, user_id, product_id, quantity, variant_id=None):
        user_oid = ObjectId(user_id)
        prod_oid = ObjectId(product_id)
        var_oid = ObjectId(variant_id) if variant_id else None

        # Tìm sản phẩm trùng cả product_id VÀ variant_id
        cart = await self.collection.find_one({
            "user_id": user_oid,
            "items": {
                "$elemMatch": {
                    "product_id": prod_oid,
                    "variant_id": var_oid
                }
            }
        })

        if cart:
            # Cộng dồn số lượng cho đúng loại đó
            await self.collection.update_one(
                {"user_id": user_oid, "items.product_id": prod_oid, "items.variant_id": var_oid},
                {"$inc": {"items.$.quantity": quantity}}
            )
        else:
            # Thêm mới một dòng vào giỏ hàng
            new_item = {"product_id": prod_oid, "variant_id": var_oid, "quantity": quantity}
            await self.collection.update_one(
                {"user_id": user_oid},
                {"$push": {"items": new_item}},
                upsert=True
            )

    async def get_cart(self, user_id: str, db):
        cart = await self.collection.find_one({"user_id": ObjectId(user_id)})
        
        if not cart or "items" not in cart:
            return {"items": [], "total_price": 0}

        detailed_items = []
        total_cart_price = 0

        for item in cart["items"]:
            # 1. Lấy thông tin sản phẩm gốc
            product = await db["products"].find_one({"_id": item["product_id"]})
            if not product:
                continue

            item_detail = {
                "product_id": str(item["product_id"]),
                "product_name": product["name"],
                "quantity": item["quantity"],
                "image_url": str(product.get("image_url", ""))
            }

            # 2. Nếu có variant, lấy thông tin variant (giá, tên variant, ảnh riêng)
            if item.get("variant_id"):
                variant = await db["product_variants"].find_one({"_id": item["variant_id"]})
                if variant:
                    item_detail["variant_id"] = str(item["variant_id"])
                    item_detail["variant_name"] = variant["name"]
                    item_detail["price"] = variant["price"]
                    if variant.get("image_url"):
                        item_detail["image_url"] = str(variant["image_url"])
            else:
                # Nếu không có variant thì lấy giá gốc của sản phẩm (nếu bạn có để giá ở bảng product)
                item_detail["price"] = product.get("price", 0)

            # Tính tổng tiền cho item này
            item_detail["subtotal"] = item_detail["price"] * item["quantity"]
            total_cart_price += item_detail["subtotal"]
            
            detailed_items.append(item_detail)

        return {
            "items": detailed_items,
            "total_price": total_cart_price
        }

    async def remove_from_cart(self, user_id: str, product_id: str, variant_id: Optional[str] = None):
        query = {
            "product_id": ObjectId(product_id),
            "variant_id": ObjectId(variant_id) if variant_id else None
        }
        await self.collection.update_one(
            {"user_id": ObjectId(user_id)},
            {"$pull": {"items": query}}
        )
        return {"status": "success", "message": "Đã xóa sản phẩm khỏi giỏ hàng"}
    
