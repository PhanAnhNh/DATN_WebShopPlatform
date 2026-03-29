# app/routes/shipping_voucher_router.py
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from app.services.shipping_voucher_service import ShippingVoucherService
from app.models.shipping_voucher_model import ShippingVoucherCreate, ShippingVoucherUpdate
from typing import Optional

router = APIRouter(prefix="/shipping-vouchers", tags=["Shipping Vouchers"])

def get_voucher_service(db=Depends(get_database)):
    return ShippingVoucherService(db)

# ============= SHIPPER ENDPOINTS =============

@router.get("/shop")
async def get_shop_shipping_vouchers(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None
):
    """Lấy danh sách voucher vận chuyển của shop"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    # Lấy shipping unit của shop
    shipping_unit = await db["shipping_units"].find_one({"shop_id": ObjectId(current_user.shop_id)})
    if not shipping_unit:
        return {"data": [], "pagination": {"page": page, "limit": limit, "total": 0, "total_pages": 0}}
    
    service = get_voucher_service(db)
    
    return await service.get_vouchers_by_shipping_unit(
        shipping_unit_id=str(shipping_unit["_id"]),
        page=page,
        limit=limit,
        status=status,
        search=search
    )

@router.post("/shop")
async def create_shipping_voucher(
    data: ShippingVoucherCreate,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Tạo voucher vận chuyển cho shop"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    # Kiểm tra shipping unit thuộc shop
    shipping_unit = await db["shipping_units"].find_one({
        "_id": ObjectId(data.shipping_unit_id),
        "shop_id": ObjectId(current_user.shop_id)
    })
    
    if not shipping_unit:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn vị vận chuyển")
    
    service = get_voucher_service(db)
    voucher, error = await service.create_voucher(data.model_dump(), current_user.shop_id)
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    return voucher

@router.put("/shop/{voucher_id}")
async def update_shipping_voucher(
    voucher_id: str,
    data: ShippingVoucherUpdate,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật voucher vận chuyển"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    # Lấy shipping unit của shop
    shipping_unit = await db["shipping_units"].find_one({"shop_id": ObjectId(current_user.shop_id)})
    if not shipping_unit:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn vị vận chuyển")
    
    service = get_voucher_service(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    voucher, error = await service.update_voucher(
        voucher_id=voucher_id,
        shipping_unit_id=str(shipping_unit["_id"]),
        update_data=update_data
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    return voucher

@router.patch("/shop/{voucher_id}/status")
async def update_shipping_voucher_status(
    voucher_id: str,
    status: str = Query(..., regex="^(active|inactive)$"),
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật trạng thái voucher"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    # Lấy shipping unit của shop
    shipping_unit = await db["shipping_units"].find_one({"shop_id": ObjectId(current_user.shop_id)})
    if not shipping_unit:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn vị vận chuyển")
    
    service = get_voucher_service(db)
    voucher, error = await service.update_status(
        voucher_id=voucher_id,
        shipping_unit_id=str(shipping_unit["_id"]),
        status=status
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    return voucher

@router.delete("/shop/{voucher_id}")
async def delete_shipping_voucher(
    voucher_id: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Xóa voucher vận chuyển"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    # Lấy shipping unit của shop
    shipping_unit = await db["shipping_units"].find_one({"shop_id": ObjectId(current_user.shop_id)})
    if not shipping_unit:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn vị vận chuyển")
    
    service = get_voucher_service(db)
    deleted = await service.delete_voucher(
        voucher_id=voucher_id,
        shipping_unit_id=str(shipping_unit["_id"])
    )
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy voucher")
    
    return {"message": "Xóa voucher thành công"}

@router.get("/shop/stats")
async def get_shipping_voucher_stats(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Lấy thống kê voucher của shop"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy shipping unit của shop
    shipping_unit = await db["shipping_units"].find_one({"shop_id": ObjectId(current_user.shop_id)})
    if not shipping_unit:
        return {"total": 0, "active": 0, "inactive": 0, "expired": 0, "total_used": 0}
    
    service = get_voucher_service(db)
    return await service.get_stats(str(shipping_unit["_id"]))

# ============= USER ENDPOINTS =============

@router.post("/validate")
async def validate_shipping_voucher(
    code: str,
    order_total: float,
    shipping_unit_id: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Validate voucher vận chuyển cho user"""
    service = get_voucher_service(db)
    
    result = await service.validate_voucher(
        code=code,
        order_total=order_total,
        shipping_unit_id=shipping_unit_id,
        user_id=str(current_user.id)
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@router.post("/use/{voucher_id}")
async def use_shipping_voucher(
    voucher_id: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Sử dụng voucher vận chuyển"""
    service = get_voucher_service(db)
    
    success = await service.increase_usage(voucher_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Không thể sử dụng voucher")
    
    return {"message": "Sử dụng voucher thành công"}