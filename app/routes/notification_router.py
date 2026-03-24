from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.services.notification_service import NotificationService
from app.models.notifications_model import NotificationCreate, NotificationUpdate
from typing import Optional

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/")
async def get_notifications(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False)
):
    """
    Lấy danh sách thông báo của user hiện tại
    """
    service = NotificationService(db)
    return await service.get_notifications(
        str(current_user.id),
        page=page,
        limit=limit,
        unread_only=unread_only
    )

@router.get("/unread-count")
async def get_unread_count(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Lấy số lượng thông báo chưa đọc
    """
    service = NotificationService(db)
    count = await service.get_unread_count(str(current_user.id))
    return {"unread_count": count}

@router.put("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Đánh dấu thông báo đã đọc
    """
    service = NotificationService(db)
    result = await service.mark_as_read(notification_id, str(current_user.id))
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")
    return {"message": "Đã đánh dấu đã đọc"}

@router.put("/read-all")
async def mark_all_as_read(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Đánh dấu tất cả thông báo đã đọc
    """
    service = NotificationService(db)
    count = await service.mark_all_as_read(str(current_user.id))
    return {"message": f"Đã đánh dấu {count} thông báo đã đọc"}

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Xóa thông báo
    """
    service = NotificationService(db)
    result = await service.delete_notification(notification_id, str(current_user.id))
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")
    return {"message": "Đã xóa thông báo"}

@router.delete("/")
async def delete_all_notifications(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Xóa tất cả thông báo
    """
    service = NotificationService(db)
    count = await service.delete_all_notifications(str(current_user.id))
    return {"message": f"Đã xóa {count} thông báo"}