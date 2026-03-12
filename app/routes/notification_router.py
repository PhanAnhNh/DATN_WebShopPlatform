from fastapi import APIRouter, Depends
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/")
async def get_notifications(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = NotificationService(db)

    return await service.get_notifications(str(current_user.id))