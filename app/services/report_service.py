from bson import ObjectId
from datetime import datetime


class ReportService:

    def __init__(self, db):
        self.collection = db.reports

    # create report
    async def create_report(self, data: dict):

        data["created_at"] = datetime.utcnow()
        data["status"] = "pending"

        result = await self.collection.insert_one(data)

        return await self.collection.find_one({
            "_id": result.inserted_id
        })

    # get reports by type
    async def get_reports_by_type(self, target_type: str):

        reports = []

        cursor = self.collection.find({
            "target_type": target_type
        }).sort("created_at", -1)

        async for r in cursor:
            r["_id"] = str(r["_id"])
            reports.append(r)

        return reports

    # get reports of specific item
    async def get_reports_of_target(self, target_id: str):

        reports = []

        cursor = self.collection.find({
            "target_id": target_id
        })

        async for r in cursor:
            r["_id"] = str(r["_id"])
            reports.append(r)

        return reports

    # admin update report status
    async def update_report_status(self, report_id: str, status: str):

        await self.collection.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": {"status": status}}
        )

        return await self.collection.find_one({
            "_id": ObjectId(report_id)
        })

    # delete report
    async def delete_report(self, report_id: str):

        await self.collection.delete_one({
            "_id": ObjectId(report_id)
        })

        return {"message": "Report deleted"}