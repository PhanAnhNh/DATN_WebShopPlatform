from bson import ObjectId
from datetime import datetime

from app.services.admin_notification_service import AdminNotificationService

class ReportService:

    def __init__(self, db):
        self.collection = db.reports
        self.db = db
        self.admin_notification_service = AdminNotificationService(db)

    # create report
    async def create_report(self, data: dict):

        data["created_at"] = datetime.utcnow()
        data["status"] = "pending"

        result = await self.collection.insert_one(data)
        report_id = str(result.inserted_id)

        admin_users = await self.db["users"].find({"role": "admin"}).to_list(length=None)
        
        # Map target_type sang tiếng Việt
        target_labels = {
            "user": "người dùng",
            "shop": "cửa hàng",
            "post": "bài viết"
        }
        target_label = target_labels.get(data.get("target_type"), "nội dung")
        
        for admin in admin_users:
            await self.admin_notification_service.create_notification(
                user_id=str(admin["_id"]),
                type=f"report_{data.get('target_type')}",
                title=f"Báo cáo mới về {target_label}",
                message=f"Có báo cáo mới về {target_label} cần xử lý",
                reference_id=report_id
            )
            
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