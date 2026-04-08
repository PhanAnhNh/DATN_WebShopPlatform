# app/services/report_service.py
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pymongo import ReturnDocument
import math

from app.models.report_model import ReportCreate, ReportUpdate, ReportStatus, ReportType

class ReportService:
    def __init__(self, db):
        self.collection = db["reports"]
        self.posts_collection = db["social_posts"]
        self.users_collection = db["users"]
        self.notification_service = None  # Will be set later

    def set_notification_service(self, notification_service):
        self.notification_service = notification_service

    async def create_report(
        self,
        report_data: ReportCreate,
        reporter_id: str
    ) -> Dict[str, Any]:
        """
        Tạo báo cáo mới
        """
        # Kiểm tra xem đã báo cáo bài viết này chưa
        existing_report = await self.collection.find_one({
            "target_type": report_data.target_type,
            "target_id": report_data.target_id,
            "reporter_id": ObjectId(reporter_id),
            "status": {"$in": [ReportStatus.PENDING, ReportStatus.APPROVED]}
        })
        
        if existing_report:
            # Đã báo cáo trước đó
            existing_report["_id"] = str(existing_report["_id"])
            return existing_report
        
        # Tạo báo cáo mới
        new_report = report_data.dict()
        new_report["reporter_id"] = ObjectId(reporter_id)
        new_report["status"] = ReportStatus.PENDING
        new_report["created_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(new_report)
        report_id = str(result.inserted_id)
        
        # Tăng report_count của bài viết
        if report_data.target_type == "post":
            await self.posts_collection.update_one(
                {"_id": ObjectId(report_data.target_id)},
                {"$inc": {"report_count": 1}}
            )
        
        # Gửi thông báo cho admin
        if self.notification_service:
            # Lấy thông tin người báo cáo
            reporter = await self.users_collection.find_one({"_id": ObjectId(reporter_id)})
            reporter_name = reporter.get("full_name", reporter.get("username", "Người dùng"))
            
            # Gửi thông báo cho tất cả admin
            admins = await self.users_collection.find({"role": "admin"}).to_list(length=None)
            for admin in admins:
                await self.notification_service.create_notification(
                    user_id=str(admin["_id"]),
                    type="report",
                    title="Báo cáo vi phạm mới",
                    message=f"{reporter_name} đã báo cáo một bài viết với lý do: {report_data.report_type.value}",
                    reference_id=report_id,
                    image_url=None
                )
        
        new_report["_id"] = report_id
        new_report["reporter_id"] = str(new_report["reporter_id"])
        
        return new_report

    async def get_reports(
        self,
        status: Optional[ReportStatus] = None,
        report_type: Optional[ReportType] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        Lấy danh sách báo cáo (cho admin)
        """
        query = {}
        
        if status:
            query["status"] = status
        
        if report_type:
            query["report_type"] = report_type
        
        # Đếm tổng số
        total = await self.collection.count_documents(query)
        
        # Sắp xếp
        sort_direction = -1 if sort_order == "desc" else 1
        
        # Lấy danh sách
        skip = (page - 1) * limit
        cursor = self.collection.find(query).sort(sort_by, sort_direction).skip(skip).limit(limit)
        
        reports = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["reporter_id"] = str(doc["reporter_id"])
            
            # Lấy thông tin người báo cáo
            reporter = await self.users_collection.find_one({"_id": ObjectId(doc["reporter_id"])})
            if reporter:
                doc["reporter_name"] = reporter.get("full_name", reporter.get("username", "Người dùng"))
                doc["reporter_avatar"] = reporter.get("avatar_url")
            
            # Lấy thông tin bài viết bị báo cáo
            if doc["target_type"] == "post":
                target_post = await self.posts_collection.find_one({"_id": ObjectId(doc["target_id"])})
                if target_post:
                    target_author = await self.users_collection.find_one({"_id": target_post["author_id"]})
                    doc["target_author_name"] = target_author.get("full_name", target_author.get("username", "Người dùng")) if target_author else "Unknown"
                    doc["target_content_preview"] = target_post.get("content", "")[:100] if target_post.get("content") else "[Không có nội dung]"
                    doc["target_author_id"] = str(target_post["author_id"])
                    doc["target_is_active"] = target_post.get("is_active", True)
            
            reports.append(doc)
        
        return {
            "data": reports,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": math.ceil(total / limit) if total > 0 else 1
            }
        }

    async def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy chi tiết báo cáo
        """
        try:
            report = await self.collection.find_one({"_id": ObjectId(report_id)})
            if not report:
                return None
            
            report["_id"] = str(report["_id"])
            report["reporter_id"] = str(report["reporter_id"])
            
            # Lấy thông tin người báo cáo
            reporter = await self.users_collection.find_one({"_id": ObjectId(report["reporter_id"])})
            if reporter:
                report["reporter_name"] = reporter.get("full_name", reporter.get("username", "Người dùng"))
                report["reporter_avatar"] = reporter.get("avatar_url")
            
            # Lấy thông tin bài viết bị báo cáo
            if report["target_type"] == "post":
                target_post = await self.posts_collection.find_one({"_id": ObjectId(report["target_id"])})
                if target_post:
                    target_author = await self.users_collection.find_one({"_id": target_post["author_id"]})
                    report["target_post"] = {
                        "_id": str(target_post["_id"]),
                        "content": target_post.get("content", ""),
                        "images": target_post.get("images", []),
                        "author_name": target_author.get("full_name", target_author.get("username", "Người dùng")) if target_author else "Unknown",
                        "author_avatar": target_author.get("avatar_url") if target_author else None,
                        "created_at": target_post.get("created_at"),
                        "is_active": target_post.get("is_active", True),
                        "report_count": target_post.get("report_count", 0)
                    }
            
            return report
        except Exception as e:
            print(f"Error getting report: {e}")
            return None

    async def update_report_status(
        self,
        report_id: str,
        update_data: ReportUpdate,
        admin_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Cập nhật trạng thái báo cáo (admin xét duyệt)
        """
        update_dict = {
            k: v for k, v in update_data.dict().items() if v is not None
        }
        
        if update_dict.get("status") in [ReportStatus.APPROVED, ReportStatus.REJECTED, ReportStatus.RESOLVED]:
            update_dict["resolved_at"] = datetime.utcnow()
            update_dict["resolved_by"] = admin_id
        
        update_dict["updated_at"] = datetime.utcnow()
        
        # Lấy báo cáo trước khi cập nhật
        old_report = await self.collection.find_one({"_id": ObjectId(report_id)})
        if not old_report:
            return None
        
        updated_report = await self.collection.find_one_and_update(
            {"_id": ObjectId(report_id)},
            {"$set": update_dict},
            return_document=ReturnDocument.AFTER
        )
        
        if updated_report:
            updated_report["_id"] = str(updated_report["_id"])
            updated_report["reporter_id"] = str(updated_report["reporter_id"])
            
            # Xử lý khi báo cáo được duyệt (vi phạm)
            if update_dict.get("status") == ReportStatus.APPROVED and old_report.get("status") != ReportStatus.APPROVED:
                await self._handle_approved_report(updated_report, admin_id)
            
            # Xử lý khi báo cáo bị từ chối
            elif update_dict.get("status") == ReportStatus.REJECTED:
                await self._handle_rejected_report(updated_report, admin_id)
            
            return updated_report
        
        return None

    async def _handle_approved_report(self, report: Dict[str, Any], admin_id: str):
        """
        Xử lý khi báo cáo được duyệt - Ẩn bài viết
        """
        if report["target_type"] == "post":
            # Ẩn bài viết bị vi phạm
            await self.posts_collection.update_one(
                {"_id": ObjectId(report["target_id"])},
                {
                    "$set": {
                        "is_active": False,
                        "hidden_by_report": True,
                        "hidden_at": datetime.utcnow(),
                        "hidden_by_admin": admin_id
                    }
                }
            )
            
            # Gửi thông báo cho tác giả bài viết
            if self.notification_service:
                target_post = await self.posts_collection.find_one({"_id": ObjectId(report["target_id"])})
                if target_post:
                    await self.notification_service.create_notification(
                        user_id=str(target_post["author_id"]),
                        type="post_hidden",
                        title="Bài viết của bạn đã bị ẩn",
                        message=f"Bài viết của bạn đã bị ẩn do vi phạm tiêu chuẩn cộng đồng. Lý do: {report.get('report_type')}",
                        reference_id=report["target_id"],
                        image_url=None
                    )

    async def _handle_rejected_report(self, report: Dict[str, Any], admin_id: str):
        """
        Xử lý khi báo cáo bị từ chối
        """
        # Gửi thông báo cho người báo cáo
        if self.notification_service:
            await self.notification_service.create_notification(
                user_id=report["reporter_id"],
                type="report_rejected",
                title="Báo cáo của bạn đã bị từ chối",
                message=f"Báo cáo bài viết của bạn không được chấp thuận vì không đủ căn cứ vi phạm.",
                reference_id=report["_id"],
                image_url=None
            )

    async def get_report_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê báo cáo
        """
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        cursor = self.collection.aggregate(pipeline)
        stats = {
            "total": await self.collection.count_documents({}),
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "resolved": 0
        }
        
        async for doc in cursor:
            status = doc["_id"]
            count = doc["count"]
            if status == ReportStatus.PENDING:
                stats["pending"] = count
            elif status == ReportStatus.APPROVED:
                stats["approved"] = count
            elif status == ReportStatus.REJECTED:
                stats["rejected"] = count
            elif status == ReportStatus.RESOLVED:
                stats["resolved"] = count
        
        return stats