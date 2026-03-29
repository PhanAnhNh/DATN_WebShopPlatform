# app/routes/shop_settings_router.py
from fastapi import APIRouter, Depends, HTTPException
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from app.services.shop_settings_service import ShopSettingsService
from typing import Any

router = APIRouter(prefix="/shop/settings", tags=["Shop Settings"])

def get_settings_service(db=Depends(get_database)):
    return ShopSettingsService(db)

@router.get("/")
async def get_settings(
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Lấy toàn bộ cài đặt của shop"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    settings = await service.get_settings(current_user.shop_id)
    return settings

@router.put("/general")
async def update_general_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt chung"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_general_settings(current_user.shop_id, data)

@router.put("/notifications")
async def update_notification_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt thông báo"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_notification_settings(current_user.shop_id, data)

@router.put("/payment")
async def update_payment_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt thanh toán"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_payment_settings(current_user.shop_id, data)

@router.put("/shipping")
async def update_shipping_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt vận chuyển"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_shipping_settings(current_user.shop_id, data)

@router.put("/security")
async def update_security_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt bảo mật"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_security_settings(current_user.shop_id, data)

@router.put("/invoice")
async def update_invoice_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt hóa đơn"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_invoice_settings(current_user.shop_id, data)

@router.put("/social")
async def update_social_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt mạng xã hội"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_social_settings(current_user.shop_id, data)

@router.put("/seo")
async def update_seo_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt SEO"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_seo_settings(current_user.shop_id, data)