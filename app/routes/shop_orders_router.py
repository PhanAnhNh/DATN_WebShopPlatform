# app/routes/shop_orders_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from app.models.orders_model import OrderStatus
from bson import ObjectId
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter(prefix="/shop/orders", tags=["Shop Orders"])

@router.get("/")
async def get_shop_orders(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """
    Lấy danh sách đơn hàng của shop (phân trang, tìm kiếm, lọc)
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Build query - tìm đơn hàng có chứa sản phẩm của shop
    match_query = {"items.shop_id": shop_id}
    
    # Filter theo trạng thái
    if status:
        match_query["status"] = status
    
    # Filter theo ngày
    date_filter = {}
    if from_date:
        date_filter["$gte"] = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
    if to_date:
        date_filter["$lte"] = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
    if date_filter:
        match_query["created_at"] = date_filter
    
    # Tìm kiếm theo tên khách hàng hoặc mã đơn
    search_pipeline = []
    if search:
        # Tìm user theo tên
        users = await db["users"].find({
            "$or": [
                {"full_name": {"$regex": search, "$options": "i"}},
                {"username": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}}
            ]
        }).to_list(length=None)
        user_ids = [ObjectId(u["_id"]) for u in users]
        
        if user_ids:
            match_query["$or"] = [
                {"user_id": {"$in": user_ids}},
                {"_id": ObjectId(search) if len(search) == 24 else None}
            ]
        else:
            # Thử tìm theo order_id
            try:
                if len(search) == 24:
                    match_query["$or"] = [{"_id": ObjectId(search)}]
            except:
                pass
    
    # Pipeline aggregate để nhóm và lấy thông tin
    pipeline = [
        {"$match": match_query},
        {"$sort": {"created_at": -1}},
        {"$skip": (page - 1) * limit},
        {"$limit": limit},
        
        # Lookup thông tin user
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user_info"
        }},
        {"$unwind": "$user_info"},
        
        # Lookup thông tin sản phẩm
        {"$unwind": "$items"},
        {"$match": {"items.shop_id": shop_id}},
        {"$lookup": {
            "from": "products",
            "localField": "items.product_id",
            "foreignField": "_id",
            "as": "product_info"
        }},
        {"$unwind": {"path": "$product_info", "preserveNullAndEmptyArrays": True}},
        
        # Group lại
        {"$group": {
            "_id": "$_id",
            "order_data": {"$first": "$$ROOT"},
            "shop_items": {"$push": {
                "product_id": "$items.product_id",
                "product_name": "$product_info.name",
                "variant_id": "$items.variant_id",
                "variant_name": "$items.variant_name",
                "quantity": "$items.quantity",
                "price": "$items.price"
            }}
        }},
        
        # Project kết quả
        {"$project": {
            "_id": 1,
            "order_id": {"$toString": "$_id"},
            "user_id": {"$toString": "$order_data.user_id"},
            "customer_name": "$order_data.user_info.full_name",
            "customer_username": "$order_data.user_info.username",
            "customer_phone": "$order_data.user_info.phone",
            "shipping_address": "$order_data.shipping_address",
            "total_price": "$order_data.total_price",
            "status": "$order_data.status",
            "payment_status": "$order_data.payment_status",
            "created_at": "$order_data.created_at",
            "items": "$shop_items"
        }}
    ]
    
    # Đếm tổng số
    count_pipeline = [
        {"$match": match_query},
        {"$group": {"_id": "$_id"}},
        {"$count": "total"}
    ]
    count_result = await db["orders"].aggregate(count_pipeline).to_list(length=None)
    total = count_result[0]["total"] if count_result else 0
    
    orders = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    # Format response
    result = []
    for order in orders:
        order["_id"] = str(order["_id"])
        result.append(order)
    
    return {
        "data": result,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@router.get("/stats")
async def get_order_stats(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thống kê đơn hàng cho dashboard
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Thống kê theo trạng thái
    pipeline = [
        {"$match": {"items.shop_id": shop_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    
    status_stats = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    stats = {
        "pending": 0,
        "paid": 0,
        "shipped": 0,
        "completed": 0,
        "cancelled": 0,
        "total": 0
    }
    
    for stat in status_stats:
        stats[stat["_id"]] = stat["count"]
        stats["total"] += stat["count"]
    
    # Doanh thu hôm nay
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59)
    
    pipeline_revenue = [
        {"$match": {
            "items.shop_id": shop_id,
            "status": {"$in": ["paid", "shipped", "completed"]},
            "created_at": {"$gte": today_start, "$lte": today_end}
        }},
        {"$unwind": "$items"},
        {"$match": {"items.shop_id": shop_id}},
        {"$group": {
            "_id": None,
            "revenue": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}}
        }}
    ]
    
    revenue_result = await db["orders"].aggregate(pipeline_revenue).to_list(length=None)
    today_revenue = revenue_result[0]["revenue"] if revenue_result else 0
    
    stats["today_revenue"] = today_revenue
    
    return stats

@router.get("/{order_id}")
async def get_shop_order_detail(
    order_id: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Xem chi tiết đơn hàng của shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Lấy đơn hàng
    pipeline = [
        {"$match": {"_id": ObjectId(order_id), "items.shop_id": shop_id}},
        
        # Lookup thông tin user
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user_info"
        }},
        {"$unwind": "$user_info"},
        
        # Lọc sản phẩm của shop
        {"$unwind": "$items"},
        {"$match": {"items.shop_id": shop_id}},
        
        # Lookup thông tin sản phẩm
        {"$lookup": {
            "from": "products",
            "localField": "items.product_id",
            "foreignField": "_id",
            "as": "product_info"
        }},
        {"$unwind": {"path": "$product_info", "preserveNullAndEmptyArrays": True}},
        
        # Lookup thông tin variant
        {"$lookup": {
            "from": "product_variants",
            "localField": "items.variant_id",
            "foreignField": "_id",
            "as": "variant_info"
        }},
        {"$unwind": {"path": "$variant_info", "preserveNullAndEmptyArrays": True}},
        
        # Group lại
        {"$group": {
            "_id": "$_id",
            "order_data": {"$first": "$$ROOT"},
            "shop_items": {"$push": {
                "product_id": {"$toString": "$items.product_id"},
                "product_name": "$product_info.name",
                "variant_id": {"$toString": "$items.variant_id"},
                "variant_name": "$items.variant_name",
                "variant_info": "$variant_info",
                "quantity": "$items.quantity",
                "price": "$items.price"
            }}
        }},
        
        # Project kết quả
        {"$project": {
            "_id": 1,
            "order_id": {"$toString": "$_id"},
            "user_id": {"$toString": "$order_data.user_id"},
            "customer_name": "$order_data.user_info.full_name",
            "customer_username": "$order_data.user_info.username",
            "customer_phone": "$order_data.user_info.phone",
            "customer_email": "$order_data.user_info.email",
            "shipping_address": "$order_data.shipping_address",
            "total_price": "$order_data.total_price",
            "status": "$order_data.status",
            "payment_status": "$order_data.payment_status",
            "created_at": "$order_data.created_at",
            "items": "$shop_items"
        }}
    ]
    
    orders = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    if not orders:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    return orders[0]

@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    status: OrderStatus,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Cập nhật trạng thái đơn hàng
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Kiểm tra đơn hàng có chứa sản phẩm của shop không
    order = await db["orders"].find_one({
        "_id": ObjectId(order_id),
        "items.shop_id": shop_id
    })
    
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    # Cập nhật trạng thái
    result = await db["orders"].update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": status.value}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Không thể cập nhật trạng thái")
    
    # Nếu đơn hàng hoàn thành, cập nhật doanh thu shop
    if status == OrderStatus.completed:
        # Tính doanh thu từ các sản phẩm của shop
        shop_revenue = 0
        for item in order["items"]:
            if str(item["shop_id"]) == current_user.shop_id:
                shop_revenue += item["price"] * item["quantity"]
        
        await db["shops"].update_one(
            {"_id": shop_id},
            {
                "$inc": {
                    "total_revenue": shop_revenue,
                    "total_orders": 1
                }
            }
        )
    
    return {"message": "Cập nhật trạng thái thành công"}