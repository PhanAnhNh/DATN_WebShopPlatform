# app/routes/shop_statistics_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter(prefix="/shop/statistics", tags=["Shop Statistics"])

@router.get("/overview")
async def get_shop_overview(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thống kê tổng quan cho shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Đếm số lượng khách hàng đã mua hàng của shop
    pipeline_customers = [
        {"$match": {"items.shop_id": shop_id}},
        {"$group": {"_id": "$user_id"}},
        {"$count": "total"}
    ]
    customers_result = await db["orders"].aggregate(pipeline_customers).to_list(length=None)
    total_customers = customers_result[0]["total"] if customers_result else 0
    
    # Đếm tổng đơn hàng
    total_orders = await db["orders"].count_documents({"items.shop_id": shop_id})
    
    # Tính tổng doanh thu
    pipeline_revenue = [
        {"$match": {
            "items.shop_id": shop_id,
            "status": {"$in": ["paid", "shipped", "completed"]}
        }},
        {"$unwind": "$items"},
        {"$match": {"items.shop_id": shop_id}},
        {"$group": {
            "_id": None,
            "total": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}}
        }}
    ]
    revenue_result = await db["orders"].aggregate(pipeline_revenue).to_list(length=None)
    total_revenue = revenue_result[0]["total"] if revenue_result else 0
    
    # Đếm số đơn trả hàng (nếu có collection riêng)
    total_returns = 0  # Tạm thời
    
    return {
        "totalCustomers": total_customers,
        "totalOrders": total_orders,
        "totalRevenue": total_revenue,
        "totalReturns": total_returns
    }

@router.get("/revenue")
async def get_revenue_stats(
    range: str = Query("month", regex="^(week|month|year)$"),
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thống kê doanh thu theo thời gian
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    now = datetime.utcnow()
    
    if range == "week":
        # 7 ngày gần nhất
        start_date = now - timedelta(days=7)
        group_by = {"$dayOfWeek": "$created_at"}
        format_label = "%A"
    elif range == "month":
        # 30 ngày gần nhất
        start_date = now - timedelta(days=30)
        group_by = {"$dayOfMonth": "$created_at"}
        format_label = "%d/%m"
    else:  # year
        # 12 tháng gần nhất
        start_date = now - timedelta(days=365)
        group_by = {"$month": "$created_at"}
        format_label = "%m/%Y"
    
    pipeline = [
        {"$match": {
            "items.shop_id": shop_id,
            "status": {"$in": ["paid", "shipped", "completed"]},
            "created_at": {"$gte": start_date}
        }},
        {"$unwind": "$items"},
        {"$match": {"items.shop_id": shop_id}},
        {"$group": {
            "_id": group_by,
            "revenue": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    result = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    return result

@router.get("/orders/daily")
async def get_daily_orders(
    days: int = 7,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy số lượng đơn hàng theo ngày
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {"$match": {
            "items.shop_id": shop_id,
            "created_at": {"$gte": start_date}
        }},
        {"$group": {
            "_id": {
                "year": {"$year": "$created_at"},
                "month": {"$month": "$created_at"},
                "day": {"$dayOfMonth": "$created_at"}
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}
    ]
    
    result = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    return result

@router.get("/reviews")
async def get_review_stats(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thống kê đánh giá sản phẩm
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Lấy tất cả sản phẩm của shop
    products = await db["products"].find({"shop_id": shop_id}).to_list(length=None)
    product_ids = [p["_id"] for p in products]
    
    # Thống kê đánh giá
    pipeline = [
        {"$match": {"product_id": {"$in": product_ids}}},
        {"$group": {
            "_id": "$rating",
            "count": {"$sum": 1}
        }}
    ]
    
    rating_stats = await db["reviews"].aggregate(pipeline).to_list(length=None)
    
    # Tính điểm trung bình
    total_reviews = sum(stat["count"] for stat in rating_stats)
    weighted_sum = sum(stat["_id"] * stat["count"] for stat in rating_stats if stat["_id"])
    avg_rating = weighted_sum / total_reviews if total_reviews > 0 else 0
    
    # Phân loại đánh giá
    good = sum(stat["count"] for stat in rating_stats if stat["_id"] >= 4)
    normal = sum(stat["count"] for stat in rating_stats if stat["_id"] == 3)
    bad = sum(stat["count"] for stat in rating_stats if stat["_id"] <= 2)
    
    return {
        "averageRating": round(avg_rating, 1),
        "totalReviews": total_reviews,
        "reviewStats": {
            "good": good,
            "normal": normal,
            "bad": bad
        }
    }