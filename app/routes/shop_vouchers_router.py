# app/routes/shop_vouchers_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from app.services.voucher_service import VoucherService
from bson import ObjectId
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/shop/vouchers", tags=["Shop Vouchers"])

@router.get("/")
async def get_shop_vouchers(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    discount_type: Optional[str] = None
):
    """Lấy danh sách voucher của shop"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    service = VoucherService(db)
    
    # Build query
    query = {
        "shop_id": ObjectId(current_user.shop_id),
        "created_by": "shop"
    }
    
    if search:
        query["code"] = {"$regex": search, "$options": "i"}
    
    if status:
        if status == "expired":
            query["end_date"] = {"$lt": datetime.utcnow()}
        else:
            query["status"] = status
    
    if discount_type:
        query["discount_type"] = discount_type
    
    # Tính skip
    skip = (page - 1) * limit
    
    # Đếm tổng số
    total = await service.collection.count_documents(query)
    
    # Lấy danh sách
    cursor = service.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    vouchers = await cursor.to_list(length=limit)
    
    # Format response
    for v in vouchers:
        v["_id"] = str(v["_id"])
        if "shop_id" in v and v["shop_id"]:
            v["shop_id"] = str(v["shop_id"])
        if "product_id" in v and v["product_id"]:
            v["product_id"] = str(v["product_id"])
    
    return {
        "data": vouchers,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@router.post("/")
async def create_shop_voucher(
    data: dict,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Tạo voucher cho shop"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    service = VoucherService(db)
    
    # Thêm shop_id
    data["shop_id"] = current_user.shop_id
    data["created_by"] = "shop"
    
    # Kiểm tra mã code trùng
    existing = await service.collection.find_one({"code": data["code"]})
    if existing:
        raise HTTPException(status_code=400, detail="Mã voucher đã tồn tại")
    
    return await service.create_voucher(data)

@router.put("/{voucher_id}")
async def update_shop_voucher(
    voucher_id: str,
    update_data: dict,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật voucher"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    service = VoucherService(db)
    
    voucher = await service.collection.find_one({"_id": ObjectId(voucher_id)})
    if not voucher:
        raise HTTPException(status_code=404, detail="Không tìm thấy voucher")
    
    if str(voucher.get("shop_id")) != current_user.shop_id:
        raise HTTPException(status_code=403, detail="Không có quyền sửa voucher này")
    
    await service.collection.update_one(
        {"_id": ObjectId(voucher_id)},
        {"$set": update_data}
    )
    
    return {"message": "Cập nhật thành công"}

@router.put("/{voucher_id}/status")
async def update_voucher_status(
    voucher_id: str,
    status: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật trạng thái voucher"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    service = VoucherService(db)
    
    voucher = await service.collection.find_one({"_id": ObjectId(voucher_id)})
    if not voucher:
        raise HTTPException(status_code=404, detail="Không tìm thấy voucher")
    
    if str(voucher.get("shop_id")) != current_user.shop_id:
        raise HTTPException(status_code=403, detail="Không có quyền sửa voucher này")
    
    await service.collection.update_one(
        {"_id": ObjectId(voucher_id)},
        {"$set": {"status": status}}
    )
    
    return {"message": "Cập nhật trạng thái thành công"}

@router.delete("/{voucher_id}")
async def delete_shop_voucher(
    voucher_id: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """Xóa voucher"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    service = VoucherService(db)
    
    voucher = await service.collection.find_one({"_id": ObjectId(voucher_id)})
    if not voucher:
        raise HTTPException(status_code=404, detail="Không tìm thấy voucher")
    
    if str(voucher.get("shop_id")) != current_user.shop_id:
        raise HTTPException(status_code=403, detail="Không có quyền xóa voucher này")
    
    await service.collection.delete_one({"_id": ObjectId(voucher_id)})
    
    return {"message": "Xóa voucher thành công"}