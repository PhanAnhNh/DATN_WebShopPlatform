from fastapi import APIRouter, Depends, HTTPException
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from bson import ObjectId
from datetime import datetime, timedelta

router = APIRouter(prefix="/shop/dashboard", tags=["Shop Dashboard"])

@router.get("/stats")
async def get_dashboard_stats(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thống kê cho dashboard của shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Chỉ shop owner mới có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Lấy thông tin shop
    shop = await db["shops"].find_one({"_id": shop_id})
    
    # Tính toán các chỉ số
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Tổng số sản phẩm
    total_products = await db["products"].count_documents({"shop_id": shop_id})
    
    # Sản phẩm hết hàng
    out_of_stock = await db["products"].count_documents({
        "shop_id": shop_id,
        "stock": 0
    })
    
    # Tổng số đơn hàng
    pipeline_orders = [
        {"$match": {"items.shop_id": shop_id}},
        {"$count": "total"}
    ]
    orders_result = await db["orders"].aggregate(pipeline_orders).to_list(length=1)
    total_orders = orders_result[0]["total"] if orders_result else 0
    
    # Đơn hàng hôm nay
    pipeline_today = [
        {"$match": {
            "items.shop_id": shop_id,
            "created_at": {"$gte": today_start}
        }},
        {"$count": "total"}
    ]
    today_result = await db["orders"].aggregate(pipeline_today).to_list(length=1)
    today_orders = today_result[0]["total"] if today_result else 0
    
    # Doanh thu
    pipeline_revenue = [
        {"$match": {
            "items.shop_id": shop_id,
            "status": "completed"
        }},
        {"$unwind": "$items"},
        {"$match": {"items.shop_id": shop_id}},
        {"$group": {
            "_id": None,
            "total": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}}
        }}
    ]
    revenue_result = await db["orders"].aggregate(pipeline_revenue).to_list(length=1)
    total_revenue = revenue_result[0]["total"] if revenue_result else 0
    
    # Doanh thu tháng này
    pipeline_month = [
        {"$match": {
            "items.shop_id": shop_id,
            "status": "completed",
            "created_at": {"$gte": month_ago}
        }},
        {"$unwind": "$items"},
        {"$match": {"items.shop_id": shop_id}},
        {"$group": {
            "_id": None,
            "total": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}}
        }}
    ]
    month_result = await db["orders"].aggregate(pipeline_month).to_list(length=1)
    month_revenue = month_result[0]["total"] if month_result else 0
    
    return {
        "products": {
            "total": total_products,
            "out_of_stock": out_of_stock,
            "in_stock": total_products - out_of_stock
        },
        "orders": {
            "total": total_orders,
            "today": today_orders
        },
        "revenue": {
            "total": total_revenue,
            "this_month": month_revenue
        },
        "shop": {
            "name": shop["name"],
            "logo_url": shop.get("logo_url"),
            "is_verified": shop.get("is_verified", False),
            "followers_count": shop.get("followers_count", 0)
        }
    }

@router.get("/recent-activities")
async def get_recent_activities(
    limit: int = 10,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy hoạt động gần đây của shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Chỉ shop owner mới có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Lấy đơn hàng gần đây
    recent_orders = await db["orders"].find(
        {"items.shop_id": shop_id}
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    activities = []
    
    for order in recent_orders:
        activities.append({
            "type": "order",
            "description": f"Đơn hàng mới #{str(order['_id'])[-6:]}",
            "time": order["created_at"],
            "data": {
                "order_id": str(order["_id"]),
                "total": order["total_price"],
                "status": order["status"]
            }
        })
    
    # Lấy sản phẩm mới
    new_products = await db["products"].find(
        {"shop_id": shop_id}
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    
    for product in new_products:
        activities.append({
            "type": "product",
            "description": f"Sản phẩm mới: {product['name']}",
            "time": product["created_at"],
            "data": {
                "product_id": str(product["_id"]),
                "name": product["name"]
            }
        })
    
    # Sắp xếp theo thời gian
    activities.sort(key=lambda x: x["time"], reverse=True)
    
    # Format time
    for activity in activities[:limit]:
        activity["time"] = activity["time"].strftime("%d/%m/%Y %H:%M")
    
    return activities[:limit]

@router.get("/chart-data")
async def get_chart_data(
    days: int = 7,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy dữ liệu cho biểu đồ
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Chỉ shop owner mới có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    
    # Tạo mảng các ngày
    dates = []
    now = datetime.utcnow()
    for i in range(days - 1, -1, -1):
        date = now - timedelta(days=i)
        dates.append({
            "start": datetime(date.year, date.month, date.day),
            "end": datetime(date.year, date.month, date.day, 23, 59, 59),
            "label": date.strftime("%d/%m")
        })
    
    # Lấy dữ liệu đơn hàng theo ngày
    orders_data = []
    revenue_data = []
    
    for date in dates:
        # Số đơn hàng
        orders_count = await db["orders"].count_documents({
            "items.shop_id": shop_id,
            "created_at": {"$gte": date["start"], "$lte": date["end"]}
        })
        orders_data.append(orders_count)
        
        # Doanh thu
        pipeline = [
            {"$match": {
                "items.shop_id": shop_id,
                "status": "completed",
                "created_at": {"$gte": date["start"], "$lte": date["end"]}
            }},
            {"$unwind": "$items"},
            {"$match": {"items.shop_id": shop_id}},
            {"$group": {
                "_id": None,
                "total": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}}
            }}
        ]
        revenue_result = await db["orders"].aggregate(pipeline).to_list(length=1)
        revenue_data.append(revenue_result[0]["total"] if revenue_result else 0)
    
    return {
        "labels": [d["label"] for d in dates],
        "orders": orders_data,
        "revenue": revenue_data
    }