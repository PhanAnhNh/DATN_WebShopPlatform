# app/routes/admin_shops_router.py
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.db.mongodb import get_database
from app.services.shop_service import ShopService
from app.core.security import get_current_user
from app.models.shops_model import ShopUpdate, ShopInDB

router = APIRouter(prefix="/admin/shops", tags=["Admin Shops"])

def get_shop_service(db = Depends(get_database)):
    return ShopService(db)

@router.get("/")  # ← Bỏ response_model=List[ShopInDB]
async def admin_get_all_shops(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: ShopService = Depends(get_shop_service),
    current_user = Depends(get_current_user)
):
    """Admin lấy tất cả shops (không cần filter)"""
    if getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    shops = await service.list_shops(skip, limit)
    return shops

@router.put("/{shop_id}")
async def admin_update_shop(
    shop_id: str,
    shop_in: ShopUpdate,
    service: ShopService = Depends(get_shop_service),
    current_user = Depends(get_current_user)
):
    """Admin cập nhật shop (không cần check owner)"""
    if getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Chuyển đổi dữ liệu
    update_dict = shop_in.model_dump(exclude_unset=True)
    
    # ✅ Nếu có location_id và là string, convert sang ObjectId
    if "location_id" in update_dict and update_dict["location_id"]:
        try:
            update_dict["location_id"] = ObjectId(update_dict["location_id"])
        except:
            pass
    
    updated_shop = await service.update_shop_admin(shop_id, update_dict)
    if not updated_shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    return updated_shop

@router.delete("/{shop_id}")
async def admin_delete_shop(
    shop_id: str,
    service: ShopService = Depends(get_shop_service),
    current_user = Depends(get_current_user)
):
    """Admin xóa shop"""
    if getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    result = await service.delete_shop_admin(shop_id)
    if not result:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    return {"message": "Xóa shop thành công"}

@router.put("/{shop_id}/status")
async def admin_toggle_shop_status(
    shop_id: str,
    status: str,
    service: ShopService = Depends(get_shop_service),
    current_user = Depends(get_current_user)
):
    """Admin thay đổi trạng thái shop"""
    if getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # SỬA: Gọi hàm update_shop_status_admin thay vì update_shop_admin
    updated_shop = await service.update_shop_status_admin(shop_id, status)
    if not updated_shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    return {"message": "Cập nhật trạng thái thành công"}