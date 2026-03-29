# app/routes/admin_settings_router.py
from fastapi import APIRouter, Depends, HTTPException
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.services.admin_permission import get_current_admin
from app.services.admin_settings_service import AdminSettingsService
from pydantic import BaseModel

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])

class SettingsUpdate(BaseModel):
    language: str | None = None
    date_format: str | None = None
    time_format: str | None = None
    theme: str | None = None
    timezone: str | None = None

@router.get("/")
async def get_admin_settings(
    db = Depends(get_database),
    admin = Depends(get_current_admin)
):
    service = AdminSettingsService(db)
    return await service.get_settings()

@router.put("/")
async def update_admin_settings(
    data: SettingsUpdate,
    db = Depends(get_database),
    admin = Depends(get_current_admin)
):
    service = AdminSettingsService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    return await service.update_settings(update_data)