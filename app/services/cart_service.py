# services/cart_service.py
from typing import Optional
from bson import ObjectId

class CartService:

    def __init__(self, db):
        self.collection = db["carts"]
        self.db = db  # Lưu db để sử dụng trong các method khác

    async def add_to_cart(self, user_id, product_id, quantity, variant_id=None, shop_id=None):
        """
        Thêm sản phẩm vào giỏ hàng
        """
        user_oid = ObjectId(user_id)
        prod_oid = ObjectId(product_id)
        var_oid = ObjectId(variant_id) if variant_id else None
        
        # Nếu không có shop_id được truyền vào, lấy từ product
        if not shop_id:
            product = await self.db["products"].find_one({"_id": prod_oid})
            if product and product.get("shop_id"):
                shop_id = str(product["shop_id"])
        
        # Kiểm tra xem sản phẩm đã tồn tại trong giỏ chưa
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
            # Cập nhật số lượng nếu đã tồn tại
            await self.collection.update_one(
                {
                    "user_id": user_oid, 
                    "items.product_id": prod_oid, 
                    "items.variant_id": var_oid
                },
                {"$inc": {"items.$.quantity": quantity}}
            )
        else:
            # Thêm mới với shop_id
            new_item = {
                "product_id": prod_oid, 
                "variant_id": var_oid, 
                "quantity": quantity,
                "shop_id": ObjectId(shop_id) if shop_id else None
            }
            await self.collection.update_one(
                {"user_id": user_oid},
                {"$push": {"items": new_item}},
                upsert=True
            )
        
        return {"status": "success", "message": "Đã thêm vào giỏ hàng"}

    async def get_cart(self, user_id: str, db):
        cart = await self.collection.find_one({"user_id": ObjectId(user_id)})
        
        if not cart or "items" not in cart:
            return {"items": [], "total_price": 0}

        detailed_items = []
        total_cart_price = 0

        for item in cart["items"]:
            product = await db["products"].find_one({"_id": item["product_id"]})
            if not product:
                continue

            item_detail = {
                "product_id": str(item["product_id"]),
                "product_name": product["name"],
                "quantity": item["quantity"],
                "image_url": str(product.get("image_url", "")),
                "shop_id": str(item.get("shop_id")) if item.get("shop_id") else None
            }

            if item.get("variant_id"):
                variant = await db["product_variants"].find_one({"_id": item["variant_id"]})
                if variant:
                    item_detail["variant_id"] = str(item["variant_id"])
                    item_detail["variant_name"] = variant["name"]
                    item_detail["price"] = variant["price"]
                    if variant.get("image_url"):
                        item_detail["image_url"] = str(variant["image_url"])
            else:
                item_detail["price"] = product.get("price", 0)

            item_detail["subtotal"] = item_detail["price"] * item["quantity"]
            total_cart_price += item_detail["subtotal"]
            
            detailed_items.append(item_detail)

        return {
            "items": detailed_items,
            "total_price": total_cart_price,
            "item_count": len(detailed_items)
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