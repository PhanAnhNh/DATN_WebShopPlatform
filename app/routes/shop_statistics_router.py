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
    
    shop_orders = await db["orders"].find(
        {"items.shop_id": shop_id}
    ).to_list(length=None)
    
    order_ids = [order["_id"] for order in shop_orders]
    
    # Đếm số lượng yêu cầu đổi trả đã được duyệt/hoàn thành
    total_returns = await db["returns"].count_documents({
        "order_id": {"$in": order_ids},
        "status": {"$in": ["approved", "completed"]}  # Chỉ tính các yêu cầu đã được duyệt/hoàn thành
    })

    total_returns = await db["returns"].count_documents({
        "order_id": {"$in": order_ids},
        "status": {"$in": ["approved", "completed"]}  # Chỉ tính các yêu cầu đã được duyệt/hoàn thành
    })
    
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
        start_date = now - timedelta(days=7)
        group_by = {"$dayOfWeek": "$created_at"}
    elif range == "month":
        start_date = now - timedelta(days=30)
        group_by = {"$dayOfMonth": "$created_at"}
    else:
        start_date = now - timedelta(days=365)
        group_by = {"$month": "$created_at"}
    
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
    Lấy thống kê đánh giá shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Thống kê đánh giá từ collection "shop_reviews"
    pipeline = [
        {"$match": {"shop_id": shop_id}},
        {"$group": {
            "_id": "$rating",
            "count": {"$sum": 1}
        }}
    ]
    
    rating_stats = await db["reviews"].aggregate(pipeline).to_list(length=None)
    
    total_reviews = sum(stat["count"] for stat in rating_stats)
    weighted_sum = sum(stat["_id"] * stat["count"] for stat in rating_stats if stat["_id"])
    avg_rating = weighted_sum / total_reviews if total_reviews > 0 else 0
    
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


@router.get("/recent-reviews")
async def get_recent_reviews(
    limit: int = 5,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy danh sách bình luận gần đây của shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Lấy reviews gần đây từ collection "reviews"
    pipeline = [
        {"$match": {"shop_id": shop_id}},
        {"$sort": {"created_at": -1}},
        {"$limit": limit},

        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user_info"
        }},
        {"$unwind": {
            "path": "$user_info",
            "preserveNullAndEmptyArrays": True
        }},
        {"$project": {
            "rating": 1,
            "comment": 1,
            "created_at": 1,
            "user_name": {
                "$ifNull": [
                    "$user_info.full_name",
                    "$user_name",
                    "$user_info.username"
                ]
            },
            "avatar_url": {
                "$ifNull": ["$user_info.avatar_url", "$user_avatar"]
            }
        }}
    ]
    
    reviews = await db["reviews"].aggregate(pipeline).to_list(length=None)
    
    for review in reviews:
        review["_id"] = str(review["_id"]) if "_id" in review else None
    
    print(f"Found {len(reviews)} recent shop reviews")
    for review in reviews:
        print(f"Review: {review}")
    
    return reviews


@router.get("/debug/shop-reviews")
async def debug_shop_reviews(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Debug: Kiểm tra dữ liệu shop_reviews
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    total_reviews = await db["reviews"].count_documents({"shop_id": shop_id})
    
    sample_reviews = await db["reviews"].find({"shop_id": shop_id}).limit(5).to_list(length=None)
    
    return {
        "shop_id": str(shop_id),
        "total_reviews": total_reviews,
        "sample_reviews": [
            {
                "_id": str(r["_id"]),
                "shop_id": str(r["shop_id"]),
                "user_id": str(r["user_id"]),
                "user_name": r.get("user_name"),
                "rating": r.get("rating"),
                "comment": r.get("comment"),
                "created_at": r.get("created_at")
            }
            for r in sample_reviews
        ]
    }

@router.get("/export")
async def export_statistics(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Xuất báo cáo thống kê ra Excel
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    overview = await get_shop_overview(db, current_user)
    revenue = await get_revenue_stats("year", db, current_user)
    reviews = await get_review_stats(db, current_user)
    recent_reviews = await get_recent_reviews(10, db, current_user)
    
    return {
        "overview": overview,
        "revenue": revenue,
        "reviews": reviews,
        "recent_reviews": recent_reviews
    }