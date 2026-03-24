# app/routes/orders_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.services.order_service import OrderService
from app.models.orders_model import OrderCreate, OrderStatus
from app.core.security import get_current_user
from bson import ObjectId
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/")
async def create_order(
    order: OrderCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = OrderService(db)
    return await service.create_order(
        str(current_user.id),
        order.model_dump()
    )


@router.get("/my")
async def my_orders(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """
    Lấy danh sách đơn hàng của user hiện tại với phân trang
    """
    service = OrderService(db)
    
    # Build query
    query = {"user_id": ObjectId(current_user.id)}
    
    # Filter theo trạng thái
    if status:
        query["status"] = status
    
    # Filter theo ngày
    if from_date or to_date:
        date_filter = {}
        if from_date:
            date_filter["$gte"] = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        if to_date:
            date_filter["$lte"] = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        if date_filter:
            query["created_at"] = date_filter
    
    # Tìm kiếm theo mã đơn
    if search:
        try:
            if len(search) == 24:
                query["_id"] = ObjectId(search)
        except:
            pass
    
    # Đếm tổng số
    total = await db["orders"].count_documents(query)
    
    # Lấy orders với phân trang
    cursor = db["orders"].find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)
    
    orders = []
    async for order in cursor:
        # Chuyển đổi ObjectId sang string
        order["_id"] = str(order["_id"])
        order["user_id"] = str(order["user_id"])
        
        # Thêm total_price để tương thích với frontend
        order["total_price"] = order.get("total_amount", 0)
        
        # Chuyển đổi items
        for item in order.get("items", []):
            item["product_id"] = str(item["product_id"])
            item["shop_id"] = str(item["shop_id"])
            if item.get("variant_id"):
                item["variant_id"] = str(item["variant_id"])
        
        # Chuyển đổi voucher
        if order.get("voucher") and order["voucher"].get("id"):
            order["voucher"]["id"] = str(order["voucher"]["id"])
        
        orders.append(order)
    
    return {
        "data": orders,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1
        }
    }


@router.get("/stats")
async def get_order_stats(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Lấy thống kê đơn hàng của user
    """
    user_id = ObjectId(current_user.id)
    
    # Thống kê theo trạng thái
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    
    status_stats = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    stats = {
        "total": 0,
        "pending": 0,
        "paid": 0,
        "shipped": 0,
        "completed": 0,
        "cancelled": 0
    }
    
    for stat in status_stats:
        status = stat["_id"]
        if status in stats:
            stats[status] = stat["count"]
        stats["total"] += stat["count"]
    
    return stats


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Lấy chi tiết đơn hàng của user hiện tại
    """
    try:
        # Lấy đơn hàng
        order = await db["orders"].find_one({
            "_id": ObjectId(order_id),
            "user_id": ObjectId(current_user.id)
        })
    except:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    # Chuyển đổi ObjectId sang string
    order["_id"] = str(order["_id"])
    order["user_id"] = str(order["user_id"])
    
    # Thêm total_price để tương thích với frontend
    order["total_price"] = order.get("total_amount", 0)
    
    # Chuyển đổi items
    for item in order.get("items", []):
        item["product_id"] = str(item["product_id"])
        item["shop_id"] = str(item["shop_id"])
        if item.get("variant_id"):
            item["variant_id"] = str(item["variant_id"])
    
    # Chuyển đổi voucher
    if order.get("voucher") and order["voucher"].get("id"):
        order["voucher"]["id"] = str(order["voucher"]["id"])
    
    # Thêm customer info nếu có
    user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
    if user:
        order["customer_name"] = user.get("full_name", user.get("username", ""))
        order["customer_phone"] = user.get("phone", "")
        order["customer_email"] = user.get("email", "")
    
    return order


@router.put("/{order_id}/status")
async def update_status(
    order_id: str,
    status: OrderStatus,
    db = Depends(get_database)
):
    service = OrderService(db)
    return await service.update_order_status(order_id, status)


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = OrderService(db)
    try:
        return await service.cancel_order(order_id, str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))