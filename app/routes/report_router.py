# app/routes/report_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.db.mongodb import get_database
from app.core.security import get_current_user, get_current_admin, CurrentUser
from app.services.report_service import ReportService
from app.models.report_model import ReportCreate, ReportUpdate, ReportStatus, ReportType

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.post("/")
async def create_report(
    report_data: ReportCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Người dùng báo cáo bài viết
    """
    service = ReportService(db)
    
    # Kiểm tra bài viết tồn tại
    from app.services.social_posts_service import SocialPostService
    post_service = SocialPostService(db)
    post = await post_service.get_post_by_id(report_data.target_id)
    
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    
    # Không cho phép báo cáo bài viết của chính mình
    if str(post["author_id"]) == str(current_user.id):
        raise HTTPException(status_code=400, detail="Bạn không thể báo cáo bài viết của chính mình")
    
    report = await service.create_report(report_data, str(current_user.id))
    return {"message": "Đã gửi báo cáo thành công", "report_id": report["_id"]}

@router.get("/admin/list")
async def get_reports_admin(
    status: Optional[ReportStatus] = None,
    report_type: Optional[ReportType] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_admin),
    db = Depends(get_database)
):
    """
    Admin lấy danh sách báo cáo
    """
    service = ReportService(db)
    result = await service.get_reports(
        status=status,
        report_type=report_type,
        page=page,
        limit=limit
    )
    return result

# QUAN TRỌNG: Đặt route /admin/stats TRƯỚC /admin/{report_id}
@router.get("/admin/stats")
async def get_report_stats_admin(
    current_user: CurrentUser = Depends(get_current_admin),
    db = Depends(get_database)
):
    """
    Admin lấy thống kê báo cáo
    """
    service = ReportService(db)
    stats = await service.get_report_stats()
    return stats

# Route này phải để SAU cùng
@router.get("/admin/{report_id}")
async def get_report_detail(
    report_id: str,
    current_user: CurrentUser = Depends(get_current_admin),
    db = Depends(get_database)
):
    """
    Admin xem chi tiết báo cáo
    """
    service = ReportService(db)
    report = await service.get_report_by_id(report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo")
    
    return report

@router.put("/admin/{report_id}")
async def update_report_status(
    report_id: str,
    update_data: ReportUpdate,
    current_user: CurrentUser = Depends(get_current_admin),
    db = Depends(get_database)
):
    """
    Admin xét duyệt báo cáo
    """
    service = ReportService(db)
    
    report = await service.update_report_status(
        report_id=report_id,
        update_data=update_data,
        admin_id=str(current_user.id)
    )
    
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy báo cáo")
    
    message = ""
    if update_data.status == ReportStatus.APPROVED:
        message = "Đã xác nhận vi phạm. Bài viết đã bị ẩn."
    elif update_data.status == ReportStatus.REJECTED:
        message = "Đã từ chối báo cáo. Bài viết vẫn hiển thị bình thường."
    else:
        message = "Đã cập nhật trạng thái báo cáo"
    
    return {"message": message, "report": report}