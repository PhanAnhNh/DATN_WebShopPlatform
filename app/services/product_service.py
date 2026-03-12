from bson import ObjectId
from datetime import datetime
from typing import List
import qrcode
import os

class ProductService:

    def __init__(self, db):
        self.db = db
        self.collection = db["products"]

    async def create_product(self, product_data: dict):
        product_data["shop_id"] = ObjectId(product_data["shop_id"])
        product_data["created_at"] = datetime.utcnow()
        product_data["category_id"] = ObjectId(product_data["category_id"])

        result = await self.collection.insert_one(product_data)
        product_id = str(result.inserted_id)

        # Tạo QR code (Nên dùng path tuyệt đối hoặc cấu hình static path)
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

        product_data["_id"] = product_id
        product_data["variants"] = []
        product_data["shop_id"] = str(product_data["shop_id"])
        product_data["qr_code_url"] = qr_path
        return product_data

    async def get_products(self, limit=20, skip=0):
        cursor = self.collection.find().skip(skip).limit(limit)
        products = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"]) # Cho Pydantic alias
            doc["_id"] = str(doc["_id"])
            doc["shop_id"] = str(doc["shop_id"])
            # Cần thêm dòng này:
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

        # TỰ ĐỘNG LẤY VARIANTS KÈM THEO
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