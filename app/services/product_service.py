# app/services/product_service.py
from bson import ObjectId
from datetime import datetime
from typing import List
import qrcode
import os

class ProductService:

    def __init__(self, db):
        self.db = db
        self.collection = db["products"]
        self.variant_collection = db["product_variants"]

    async def create_product(self, product_data: dict):
        # Tách variants ra khỏi product_data
        variants_data = product_data.pop("variants", [])
        
        # Xử lý price và stock
        price = product_data.pop("price", None)
        stock = product_data.pop("stock", 0)
        
        # Tạo product
        product_data["shop_id"] = ObjectId(product_data["shop_id"])
        product_data["created_at"] = datetime.utcnow()
        product_data["category_id"] = ObjectId(product_data["category_id"])
        
        # Nếu có variants, tính tổng stock và bỏ qua price/stock riêng
        if variants_data:
            total_stock = sum(v.get("stock", 0) for v in variants_data)
            product_data["stock"] = total_stock
            # Không lưu price ở product nếu có variants
        else:
            # Nếu không có variants, dùng price và stock từ form
            if price is not None:
                product_data["price"] = price
            product_data["stock"] = stock

        result = await self.collection.insert_one(product_data)
        product_id = str(result.inserted_id)

        # Tạo QR code
        qr_url = f"http://localhost:8000/products/{product_id}/trace"
        img = qrcode.make(qr_url)
        
        dir_path = "static/qr_codes"
        os.makedirs(dir_path, exist_ok=True)
        qr_path = f"{dir_path}/{product_id}.png"
        img.save(qr_path)

        # Update lại đường dẫn QR
        await self.collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"qr_code_url": qr_path}}
        )

        # Tạo variants nếu có - THÊM product_id VÀO ĐÂY
        created_variants = []
        if variants_data:
            for variant in variants_data:
                # Thêm product_id vào variant data
                variant["product_id"] = ObjectId(product_id)
                variant["created_at"] = datetime.utcnow()
                
                var_result = await self.variant_collection.insert_one(variant)
                created_variant = await self.variant_collection.find_one({"_id": var_result.inserted_id})
                
                # Convert ObjectId to string
                created_variant["_id"] = str(created_variant["_id"])
                created_variant["product_id"] = str(created_variant["product_id"])
                created_variants.append(created_variant)

        # Lấy sản phẩm vừa tạo
        product = await self.collection.find_one({"_id": result.inserted_id})
        
        # CHUYỂN ĐỔI TẤT CẢ ObjectId SANG STRING
        product["_id"] = str(product["_id"])
        product["shop_id"] = str(product["shop_id"])
        product["category_id"] = str(product["category_id"])
        
        # Thêm trường id cho response
        product["id"] = product["_id"]
        
        # Thêm variants vào response
        product["variants"] = created_variants
        product["qr_code_url"] = qr_path
        
        return product

    async def get_products(self, limit=20, skip=0):
        cursor = self.collection.find().skip(skip).limit(limit)
        products = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            doc["_id"] = str(doc["_id"])
            doc["shop_id"] = str(doc["shop_id"])
            if "category_id" in doc:
                doc["category_id"] = str(doc["category_id"])
            products.append(doc)
        return products

    async def update_product(self, product_id, update_data):
        # 1. Convert category_id sang ObjectId TRƯỚC khi update
        if "category_id" in update_data:
            update_data["category_id"] = ObjectId(update_data["category_id"])

        # 2. Sau đó mới thực hiện update
        await self.collection.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": update_data}
        )
        return await self.get_product(product_id)

    async def get_product(self, product_id: str):
        product = await self.collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            return None

        product["id"] = str(product["_id"])
        product["_id"] = str(product["_id"])
        product["shop_id"] = str(product["shop_id"])
        product["category_id"] = str(product["category_id"])

        # Lấy variants
        variant_cursor = self.db["product_variants"].find({"product_id": ObjectId(product_id)})
        variants = []
        async for v in variant_cursor:
            v["id"] = str(v["_id"])
            v["_id"] = str(v["_id"])
            v["product_id"] = str(v["product_id"])
            variants.append(v)
        
        product["variants"] = variants
        return product

    async def delete_product(self, product_id):
        await self.collection.delete_one({"_id": ObjectId(product_id)})
        return {"message": "Product deleted"}