from bson import ObjectId
from datetime import datetime


class CategoryService:

    def __init__(self, db):
        self.collection = db["categories"]


    async def create_category(self, data: dict):

        if data.get("parent_id"):
            data["parent_id"] = ObjectId(data["parent_id"])

        data["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(data)

        category = await self.collection.find_one({
            "_id": result.inserted_id
        })

        category["_id"] = str(category["_id"])

        if category.get("parent_id"):
            category["parent_id"] = str(category["parent_id"])

        return category


    async def get_categories(self):

        categories = []

        cursor = self.collection.find()

        async for c in cursor:

            c["_id"] = str(c["_id"])

            if c.get("parent_id"):
                c["parent_id"] = str(c["parent_id"])

            categories.append(c)

        return categories


    async def get_category(self, category_id: str):

        category = await self.collection.find_one({
            "_id": ObjectId(category_id)
        })

        if not category:
            return None

        category["_id"] = str(category["_id"])

        if category.get("parent_id"):
            category["parent_id"] = str(category["parent_id"])

        return category


    async def update_category(self, category_id: str, data: dict):

        if data.get("parent_id"):
            data["parent_id"] = ObjectId(data["parent_id"])

        await self.collection.update_one(
            {"_id": ObjectId(category_id)},
            {"$set": data}
        )

        return await self.get_category(category_id)


    async def delete_category(self, category_id: str):

        await self.collection.delete_one({
            "_id": ObjectId(category_id)
        })

        return {"message": "Category deleted"}