from bson import ObjectId
from datetime import datetime


class ProductVariantService:

    def __init__(self, db):
        self.collection = db["product_variants"]

    async def create_variant(self, data: dict):

        data["product_id"] = ObjectId(data["product_id"])
        data["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(data)

        variant = await self.collection.find_one({
             "_id": result.inserted_id
        })

        variant["_id"] = str(variant["_id"])
        variant["product_id"] = str(variant["product_id"])

        return variant
        
    async def get_variants_by_product(self, product_id: str):

        variants = []

        cursor = self.collection.find({
            "product_id": ObjectId(product_id)
        })

        async for v in cursor:

            v["_id"] = str(v["_id"])
            v["product_id"] = str(v["product_id"])

            variants.append(v)

        return variants
        
    async def get_variant(self, variant_id: str):

        variant = await self.collection.find_one({
            "_id": ObjectId(variant_id)
        })

        if not variant:
            return None

        variant["_id"] = str(variant["_id"])
        variant["product_id"] = str(variant["product_id"])

        return variant
        
    async def update_variant(self, variant_id: str, data: dict):
        # Nếu update cả product_id (hiếm khi xảy ra nhưng vẫn nên phòng ngừa)
        if "product_id" in data:
            data["product_id"] = ObjectId(data["product_id"])

        await self.collection.update_one(
            {"_id": ObjectId(variant_id)},
            {"$set": data}
        )
        return await self.get_variant(variant_id)
        
    async def delete_variant(self, variant_id: str):

        await self.collection.delete_one({
            "_id": ObjectId(variant_id)
        })

        return {"message": "Variant deleted"}