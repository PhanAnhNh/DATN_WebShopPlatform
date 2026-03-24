# app/routes/admin_notification_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.core.security import get_current_admin
from app.services.admin_notification_service import AdminNotificationService
from typing import Optional

router = APIRouter(prefix="/admin/notifications", tags=["Admin Notifications"])

@router.get("/")
async def get_admin_notifications(
    db = Depends(get_database),
    current_admin = Depends(get_current_admin),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False)
):
    """
    Lấy danh sách thông báo của admin
    """
    service = AdminNotificationService(db)
    return await service.get_notifications(
        str(current_admin.id),
        page=page,
        limit=limit,
        unread_only=unread_only
    )

@router.get("/unread-count")
async def get_admin_unread_count(
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """
    Lấy số lượng thông báo admin chưa đọc
    """
    service = AdminNotificationService(db)
    count = await service.get_unread_count(str(current_admin.id))
    return {"unread_count": count}

@router.put("/{notification_id}/read")
async def mark_admin_notification_as_read(
    notification_id: str,
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """
    Đánh dấu thông báo admin đã đọc
    """
    service = AdminNotificationService(db)
    result = await service.mark_as_read(notification_id, str(current_admin.id))
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")
    return {"message": "Đã đánh dấu đã đọc"}

@router.put("/read-all")
async def mark_all_admin_notifications_as_read(
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """
    Đánh dấu tất cả thông báo admin đã đọc
    """
    service = AdminNotificationService(db)
    count = await service.mark_all_as_read(str(current_admin.id))
    return {"message": f"Đã đánh dấu {count} thông báo đã đọc"}

@router.delete("/{notification_id}")
async def delete_admin_notification(
    notification_id: str,
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """
    Xóa thông báo admin
    """
    service = AdminNotificationService(db)
    result = await service.delete_notification(notification_id, str(current_admin.id))
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")
    return {"message": "Đã xóa thông báo"}

@router.delete("/")
async def delete_all_admin_notifications(
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """
    Xóa tất cả thông báo admin
    """
    service = AdminNotificationService(db)
    count = await service.delete_all_notifications(str(current_admin.id))
    return {"message": f"Đã xóa {count} thông báo"}