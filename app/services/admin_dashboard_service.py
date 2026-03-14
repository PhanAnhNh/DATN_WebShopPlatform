from datetime import datetime, timedelta


class AdminService:

    def __init__(self, db):
        self.db = db

    async def get_dashboard_stats(self):

        users = await self.db["users"].count_documents({})
        shops = await self.db["shops"].count_documents({})
        posts = await self.db["social_posts"].count_documents({})
        reports = await self.db["reports"].count_documents({})

        return {
            "total_users": users,
            "total_shops": shops,
            "total_posts": posts,
            "total_reports": reports
        }

    async def get_category_stats(self):

        pipeline = [
            {
                "$group": {
                    "_id": "$category",
                    "count": {"$sum": 1}
                }
            }
        ]

        result = []

        total_posts = await self.db["social_posts"].count_documents({})

        async for item in self.db["social_posts"].aggregate(pipeline):

            percentage = (item["count"] / total_posts) * 100 if total_posts > 0 else 0

            result.append({
                "category": item["_id"],
                "count": item["count"],
                "percentage": round(percentage, 2)
            })

        return result

    async def get_new_users(self):

        last_week = datetime.utcnow() - timedelta(days=7)

        users = self.db["users"].find(
            {"created_at": {"$gte": last_week}}
        ).sort("created_at", -1)

        result = []

        async for u in users:
            u["_id"] = str(u["_id"])
            result.append(u)

        return result

    async def get_new_shops(self):

        shops = self.db["shops"].find().sort("created_at", -1).limit(10)

        result = []

        async for s in shops:
            s["_id"] = str(s["_id"])
            result.append(s)

        return result