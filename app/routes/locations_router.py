# app/api/v1/endpoints/locations.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from app.schemas.locations import (
    LocationCreate, LocationUpdate,
    ProvinceCreate, ProvinceUpdate,
)
from app.services.location_service import location_service
from app.core.security import get_current_admin, get_current_user, CurrentUser

router = APIRouter(prefix="/locations", tags=["Locations"])

# ========== Location Endpoints ==========

@router.get("/nearby")
async def get_nearby_locations(
    lat: float = Query(..., description="Vĩ độ"),
    lng: float = Query(..., description="Kinh độ"),
    radius_km: float = Query(10, ge=0, le=100, description="Bán kính (km)"),
    category: Optional[str] = Query(None, description="Loại địa điểm"),
    limit: int = Query(50, ge=1, le=200)
):
    """Tìm địa điểm gần vị trí hiện tại"""
    locations = await location_service.get_nearby_locations(
        lat=lat, lng=lng, radius_km=radius_km,
        category=category, limit=limit
    )
    return {"data": locations, "total": len(locations)}

@router.get("/province/{province_id}")
async def get_locations_by_province(
    province_id: str,
    limit: int = Query(500, ge=1, le=1000),   # ← Tăng lên
    page: int = Query(1, ge=1)
):
    """Lấy danh sách địa điểm theo tỉnh (dùng cho Admin)"""
    print(f"=== DEBUG: province_id = {province_id}, limit = {limit}, page = {page} ===")
    
    try:
        result = await location_service.get_locations_by_province(
            province_id=province_id, limit=limit, page=page
        )
        return result
    except Exception as e:
        print(f"=== ERROR in get_locations_by_province: {e} ===")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{location_id}")
async def get_location(location_id: str):
    """Lấy chi tiết địa điểm"""
    location = await location_service.get_location(location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa điểm")
    return location

@router.post("/")
async def create_location(
    location_data: LocationCreate,
    current_user: CurrentUser = Depends(get_current_admin)
):
    """Tạo địa điểm mới (Chỉ admin)"""
    print(f"=== Creating location with data: {location_data} ===")
    location = await location_service.create_location(
        location_data=location_data,
        user_id=current_user.id
    )
    return location

@router.put("/{location_id}")
async def update_location(
    location_id: str,
    update_data: LocationUpdate,
    current_user: CurrentUser = Depends(get_current_admin)
):
    """Cập nhật địa điểm (Chỉ admin)"""
    location = await location_service.update_location(location_id, update_data)
    if not location:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa điểm")
    return location

@router.delete("/{location_id}")
async def delete_location(
    location_id: str,
    hard_delete: bool = Query(False, description="Xóa vĩnh viễn"),
    current_user: CurrentUser = Depends(get_current_admin)
):
    """Xóa địa điểm (Chỉ admin)"""
    success = await location_service.delete_location(location_id, soft_delete=not hard_delete)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa điểm")
    return {"message": "Xóa thành công"}

# ========== Province Endpoints ==========

@router.get("/provinces/all")
async def get_all_provinces(
    status: Optional[str] = Query("active", description="active, inactive, all")
):
    """Lấy danh sách tất cả tỉnh thành"""
    if status == "all":
        status = None
    provinces = await location_service.get_all_provinces(status)
    return provinces

@router.get("/provinces/{province_id}")
async def get_province(province_id: str):
    """Lấy chi tiết tỉnh thành"""
    province = await location_service.get_province(province_id)
    if not province:
        raise HTTPException(status_code=404, detail="Không tìm thấy tỉnh thành")
    return province

@router.post("/provinces")
async def create_province(
    province_data: ProvinceCreate,
    current_user: CurrentUser = Depends(get_current_admin)
):
    """Tạo tỉnh thành mới (Chỉ admin)"""
    province = await location_service.create_province(province_data)
    return province

@router.put("/provinces/{province_id}")
async def update_province(
    province_id: str,
    update_data: ProvinceUpdate,
    current_user: CurrentUser = Depends(get_current_admin)
):
    """Cập nhật tỉnh thành (Chỉ admin)"""
    province = await location_service.update_province(province_id, update_data)
    if not province:
        raise HTTPException(status_code=404, detail="Không tìm thấy tỉnh thành")
    return province

@router.delete("/provinces/{province_id}")
async def delete_province(
    province_id: str,
    hard_delete: bool = Query(False, description="Xóa vĩnh viễn"),
    current_user: CurrentUser = Depends(get_current_admin)
):
    """Xóa tỉnh thành (Chỉ admin)"""
    success = await location_service.delete_province(province_id, soft_delete=not hard_delete)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy tỉnh thành")
    return {"message": "Xóa thành công"}

@router.get("/provinces/{province_id}/statistics")
async def get_province_statistics(province_id: str):
    """Lấy thống kê của tỉnh thành"""
    stats = await location_service.get_province_statistics(province_id)
    return stats