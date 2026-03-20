# app/routes/shop_settings_router.py
from fastapi import APIRouter, Depends, HTTPException
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from typing import Any, Dict

router = APIRouter(prefix="/shop/settings", tags=["Shop Settings"])

@router.get("/")
async def get_all_settings(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Lấy tất cả cài đặt của shop"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    settings = await db["shop_settings"].find_one({"shop_id": current_user.shop_id})
    
    if not settings:
        # Tạo settings mặc định
        settings = {
            "shop_id": current_user.shop_id,
            "general": {},
            "notifications": {},
            "payment": {},
            "shipping": {},
            "invoice": {},
            "security": {},
            "social": {},
            "seo": {}
        }
        await db["shop_settings"].insert_one(settings)
    
    settings["_id"] = str(settings["_id"])
    return settings

@router.get("/{tab}")
async def get_tab_settings(
    tab: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Lấy cài đặt theo tab"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    settings = await db["shop_settings"].find_one(
        {"shop_id": current_user.shop_id},
        {tab: 1}
    )
    
    return settings.get(tab, {}) if settings else {}

@router.put("/{tab}")
async def update_tab_settings(
    tab: str,
    data: Dict[str, Any],
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt theo tab"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    result = await db["shop_settings"].update_one(
        {"shop_id": current_user.shop_id},
        {"$set": {tab: data}},
        upsert=True
    )
    
    return {"message": "Cập nhật thành công"}