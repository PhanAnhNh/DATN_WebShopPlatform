# app/routes/shipping_unit_router.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from app.db.mongodb import get_database
from app.services.shipping_unit_service import ShippingUnitService
from app.models.shipping_unit_model import (
    ShippingUnitCreate, 
    ShippingUnitUpdate, 
    ShippingUnitResponse,
    ShippingUnitStatus
)
from app.core.security import get_current_shop_owner, get_current_user

router = APIRouter(prefix="/shipping-units", tags=["Shipping Units"])

# ==================== SHOP ROUTES ====================
@router.post("/shop", response_model=ShippingUnitResponse, status_code=status.HTTP_201_CREATED)
async def create_shipping_unit(
    unit_in: ShippingUnitCreate,
    db = Depends(get_database),
    current_shop = Depends(get_current_shop_owner)
):
    """Shop tạo đơn vị vận chuyển mới"""
    # Debug: In dữ liệu nhận được
    print("=== CREATE SHIPPING UNIT ===")
    print(f"Shop ID: {current_shop.shop_id}")
    print(f"Data received: {unit_in.model_dump()}")
    
    service = ShippingUnitService(db)
    
    unit_data = unit_in.model_dump()
    
    # Xử lý các field null
    if unit_data.get('logo_url') == '':
        unit_data['logo_url'] = None
    if unit_data.get('website') == '':
        unit_data['website'] = None
    if unit_data.get('phone') == '':
        unit_data['phone'] = None
    if unit_data.get('email') == '':
        unit_data['email'] = None
    
    unit, error = await service.create_shipping_unit(unit_data, current_shop.shop_id)
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return unit

@router.get("/shop/stats")
async def get_shipping_stats(
    db = Depends(get_database),
    current_shop = Depends(get_current_shop_owner)
):
    """Shop xem thống kê vận chuyển của mình"""
    service = ShippingUnitService(db)
    stats = await service.get_shop_shipping_stats(current_shop.shop_id)
    return stats

@router.get("/shop")
async def list_shipping_units(
    db = Depends(get_database),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    current_shop = Depends(get_current_shop_owner)
):
    """Shop lấy danh sách đơn vị vận chuyển của mình"""
    service = ShippingUnitService(db)
    return await service.list_shipping_units_by_shop(
        current_shop.shop_id, 
        skip, 
        limit, 
        status
    )

@router.get("/shop/{unit_id}", response_model=ShippingUnitResponse)
async def get_shipping_unit(
    unit_id: str,
    db = Depends(get_database),
    current_shop = Depends(get_current_shop_owner)
):
    """Shop lấy chi tiết đơn vị vận chuyển"""
    service = ShippingUnitService(db)
    unit = await service.get_shipping_unit_by_id(unit_id, current_shop.shop_id)
    
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn vị vận chuyển"
        )
    
    return unit

@router.put("/shop/{unit_id}", response_model=ShippingUnitResponse)
async def update_shipping_unit(
    unit_id: str,
    unit_update: ShippingUnitUpdate,
    db = Depends(get_database),
    current_shop = Depends(get_current_shop_owner)
):
    """Shop cập nhật đơn vị vận chuyển"""
    service = ShippingUnitService(db)
    
    update_data = unit_update.model_dump(exclude_unset=True)
    
    # Xử lý các field null
    if 'logo_url' in update_data and update_data['logo_url'] == '':
        update_data['logo_url'] = None
    if 'website' in update_data and update_data['website'] == '':
        update_data['website'] = None
    if 'phone' in update_data and update_data['phone'] == '':
        update_data['phone'] = None
    if 'email' in update_data and update_data['email'] == '':
        update_data['email'] = None
    
    unit, error = await service.update_shipping_unit(
        unit_id, 
        update_data, 
        current_shop.shop_id
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn vị vận chuyển"
        )
    
    return unit

@router.patch("/shop/{unit_id}/status")
async def update_shipping_unit_status(
    unit_id: str,
    status: ShippingUnitStatus,
    db = Depends(get_database),
    current_shop = Depends(get_current_shop_owner)
):
    """Shop cập nhật trạng thái đơn vị vận chuyển"""
    service = ShippingUnitService(db)
    
    unit, error = await service.update_status(unit_id, status, current_shop.shop_id)
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn vị vận chuyển"
        )
    
    return {
        "message": f"Đã cập nhật trạng thái thành {status.value}",
        "unit": unit
    }

@router.delete("/shop/{unit_id}")
async def delete_shipping_unit(
    unit_id: str,
    db = Depends(get_database),
    current_shop = Depends(get_current_shop_owner)
):
    """Shop xóa đơn vị vận chuyển"""
    service = ShippingUnitService(db)
    
    deleted, error = await service.delete_shipping_unit(unit_id, current_shop.shop_id)
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn vị vận chuyển"
        )
    
    return {"message": "Đã xóa đơn vị vận chuyển thành công"}

# ==================== PUBLIC ROUTES ====================
@router.get("/available")
async def get_available_shipping_units(
    shop_id: str = Query(..., description="ID của shop"),
    order_total: float = Query(..., ge=0),
    province: str = Query(..., min_length=2),
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy danh sách đơn vị vận chuyển khả dụng cho shop (cho khách hàng)"""
    service = ShippingUnitService(db)
    units_result = await service.list_shipping_units_by_shop(shop_id, status="active")
    
    # Tính phí cho từng đơn vị
    for unit in units_result["data"]:
        fee, _ = await service.calculate_shipping_fee(
            unit["id"], 
            order_total, 
            province, 
            shop_id
        )
        unit["calculated_fee"] = fee if fee is not None else unit["shipping_fee_base"]
        unit["is_free"] = fee == 0 if fee is not None else False
    
    # Sắp xếp theo phí ship tăng dần
    units_result["data"].sort(key=lambda x: x["calculated_fee"])
    
    return units_result