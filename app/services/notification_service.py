from datetime import datetime

from bson import ObjectId

class NotificationService:

    def __init__(self, db):
        self.collection = db["notifications"]

    async def create_notification(self, user_id, type, message, reference_id=None):

        await self.collection.insert_one({
            "user_id": ObjectId(user_id),
            "type": type,
            "message": message,
            "reference_id": reference_id,
            "is_read": False,
            "created_at": datetime.utcnow()
        })

    async def get_notifications(self, user_id):

        cursor = self.collection.find(
            {"user_id": ObjectId(user_id)}
        ).sort("created_at",-1)

        result = []

        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            result.append(doc)

        return result