from bson import ObjectId
from datetime import datetime


class ProductReviewService:

    def __init__(self, db):
        self.collection = db["product_reviews"]
        self.product_collection = db["products"]

    async def create_review(self, user_id: str, data: dict):

        data["user_id"] = ObjectId(user_id)
        data["product_id"] = ObjectId(data["product_id"])
        data["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(data)

        # update product rating
        reviews = self.collection.find({
            "product_id": ObjectId(data["product_id"])
        })

        total = 0
        count = 0

        async for r in reviews:
            total += r["rating"]
            count += 1

        avg_rating = total / count if count > 0 else 0

        await self.product_collection.update_one(
            {"_id": ObjectId(data["product_id"])},
            {
                "$set": {"rating": avg_rating},
                "$inc": {"review_count": 1}
            }
        )

        return str(result.inserted_id)

    async def get_product_reviews(self, product_id: str):

        cursor = self.collection.find({
            "product_id": ObjectId(product_id)
        }).sort("created_at", -1)

        reviews = []

        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["product_id"] = str(doc["product_id"])
            doc["user_id"] = str(doc["user_id"])

            reviews.append(doc)

        return reviews
    
    async def update_review(self, review_id: str, user_id: str, data: dict):

        review = await self.collection.find_one({
            "_id": ObjectId(review_id)
        })

        if not review:
            return None

        if str(review["user_id"]) != user_id:
            raise Exception("Not allowed")

        await self.collection.update_one(
            {"_id": ObjectId(review_id)},
            {"$set": data}
        )

        return await self.collection.find_one({
            "_id": ObjectId(review_id)
        })

    async def delete_review(self, review_id: str, user_id: str):

        review = await self.collection.find_one({
            "_id": ObjectId(review_id)
        })

        if not review:
            return None

        if str(review["user_id"]) != user_id:
            raise Exception("Not allowed")

        await self.collection.delete_one({
            "_id": ObjectId(review_id)
        })

        return {"message": "Review deleted"}