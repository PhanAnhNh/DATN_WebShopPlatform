from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from app.core.cache import invalidate_cache, get_cached, set_cached  # Thay đổi import
from app.db.mongodb import get_database
from app.models.orders_model import OrderCreate, OrderStatus, OrderUpdate
from app.core.security import get_current_user
from bson import ObjectId
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging
import json

from app.services.order_service import OrderService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orders", tags=["Orders"])


# ==================== MODELS ====================

class OrderListResponse(BaseModel):
    data: List[Dict[str, Any]]
    pagination: Dict[str, int]
    filters: Dict[str, Any]


class OrderStatsResponse(BaseModel):
    total: int
    pending: int
    paid: int
    shipped: int
    completed: int
    cancelled: int
    pending_payment: int = Field(0)
    processing: int = Field(0)
    last_30_days: Optional[int] = None


class CancelOrderResponse(BaseModel):
    status: str
    message: str
    refund_amount: Optional[float] = None


# ==================== CREATE ORDER - NO CACHE ====================

@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_order(
    order: OrderCreate,
    background_tasks: BackgroundTasks,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Create new order - NO CACHE"""
    service = OrderService(db)
    
    try:
        if not order.items:
            raise HTTPException(status_code=400, detail="Đơn hàng không có sản phẩm")
        
        if order.total_amount <= 0:
            raise HTTPException(status_code=400, detail="Tổng tiền đơn hàng không hợp lệ")
        
        result = await service.create_order(
            str(current_user.id),
            order.model_dump()
        )
        
        # Invalidate cache
        await invalidate_cache(f"user_orders:{current_user.id}:*")
        await invalidate_cache(f"order_stats:{current_user.id}")
        
        logger.info(f"✅ Order created: {result.get('order_code')}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create order: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== GET ORDERS - WITH MANUAL CACHE ====================

@router.get("/my", response_model=OrderListResponse)
async def get_my_orders(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    status: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$")
):
    """Get user orders with manual cache"""
    
    # Generate cache key from all params
    cache_key = f"user_orders:{current_user.id}:{page}:{limit}:{status}:{payment_status}:{search}:{from_date}:{to_date}:{min_amount}:{max_amount}:{sort_by}:{sort_order}"
    
    # Try to get from cache
    cached_result = await get_cached(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for orders")
        return OrderListResponse(**cached_result)
    
    # Parse dates
    def parse_date(date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            if date_str.endswith('Z'):
                date_str = date_str.replace('Z', '+00:00')
            return datetime.fromisoformat(date_str)
        except:
            return None
    
    from_date_parsed = parse_date(from_date)
    to_date_parsed = parse_date(to_date)
    
    # Build query
    query = {"user_id": ObjectId(current_user.id)}
    if status:
        query["status"] = status
    if payment_status:
        query["payment_status"] = payment_status
    
    if from_date_parsed or to_date_parsed:
        date_filter = {}
        if from_date_parsed:
            date_filter["$gte"] = from_date_parsed
        if to_date_parsed:
            date_filter["$lte"] = to_date_parsed + timedelta(days=1)
        if date_filter:
            query["created_at"] = date_filter
    
    if min_amount is not None or max_amount is not None:
        amount_filter = {}
        if min_amount is not None:
            amount_filter["$gte"] = min_amount
        if max_amount is not None:
            amount_filter["$lte"] = max_amount
        if amount_filter:
            query["total_amount"] = amount_filter
    
    if search:
        if len(search) == 24 and all(c in '0123456789abcdefABCDEF' for c in search):
            try:
                query["_id"] = ObjectId(search)
            except:
                pass
        else:
            query["_id"] = {"$regex": f".*{search}.*", "$options": "i"}
    
    # Validate sort
    allowed_sort_fields = ["created_at", "total_amount", "status", "updated_at"]
    if sort_by not in allowed_sort_fields:
        sort_by = "created_at"
    sort_direction = -1 if sort_order == "desc" else 1
    
    try:
        total = await db["orders"].count_documents(query)
        
        if total == 0:
            result_data = {
                "data": [],
                "pagination": {"page": page, "limit": limit, "total": 0, "total_pages": 0},
                "filters": {"status": status, "payment_status": payment_status}
            }
            await set_cached(cache_key, result_data, ttl=30)
            return OrderListResponse(**result_data)
        
        skip = (page - 1) * limit
        total_pages = (total + limit - 1) // limit
        
        cursor = db["orders"].find(
            query,
            {
                "_id": 1, "user_id": 1, "total_amount": 1, "status": 1,
                "payment_status": 1, "payment_method": 1, "created_at": 1,
                "items": {"$slice": 2}, "subtotal": 1, "discount": 1, "shipping_fee": 1
            }
        ).sort(sort_by, sort_direction).skip(skip).limit(limit)
        
        orders = []
        async for order in cursor:
            order_dict = {
                "_id": str(order["_id"]),
                "order_code": str(order["_id"])[-8:].upper(),
                "user_id": str(order["user_id"]),
                "total_amount": order.get("total_amount", 0),
                "subtotal": order.get("subtotal", 0),
                "discount": order.get("discount", 0),
                "shipping_fee": order.get("shipping_fee", 0),
                "status": order.get("status", "pending"),
                "payment_status": order.get("payment_status", "unpaid"),
                "payment_method": order.get("payment_method", "cod"),
                "created_at": order.get("created_at"),
                "item_count": len(order.get("items", [])),
                "items_preview": [
                    {
                        "product_name": item.get("variant_name") or item.get("product_name", "Sản phẩm"),
                        "quantity": item.get("quantity", 0),
                        "price": item.get("price", 0)
                    }
                    for item in order.get("items", [])[:2]
                ]
            }
            orders.append(order_dict)
        
        result_data = {
            "data": orders,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages
            },
            "filters": {
                "status": status,
                "payment_status": payment_status,
                "from_date": from_date,
                "to_date": to_date,
                "min_amount": min_amount,
                "max_amount": max_amount
            }
        }
        
        # Save to cache
        await set_cached(cache_key, result_data, ttl=30)
        
        return OrderListResponse(**result_data)
        
    except Exception as e:
        logger.error(f"Error fetching orders: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi khi lấy danh sách đơn hàng")


# ==================== STATS - WITH MANUAL CACHE ====================

@router.get("/stats", response_model=OrderStatsResponse)
async def get_order_stats(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365)
):
    """Get order statistics with manual cache"""
    
    cache_key = f"order_stats:{current_user.id}:{days}"
    
    # Try cache
    cached_result = await get_cached(cache_key)
    if cached_result:
        return OrderStatsResponse(**cached_result)
    
    user_id = ObjectId(current_user.id)
    days_ago = datetime.utcnow() - timedelta(days=days)
    
    try:
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        status_stats = await db["orders"].aggregate(pipeline).to_list(length=None)
        
        recent_pipeline = [
            {"$match": {"user_id": user_id, "created_at": {"$gte": days_ago}}},
            {"$count": "total"}
        ]
        recent_result = await db["orders"].aggregate(recent_pipeline).to_list(length=None)
        last_30_days = recent_result[0]["total"] if recent_result else 0
        
        stats = {
            "total": 0, "pending": 0, "paid": 0, "shipped": 0,
            "completed": 0, "cancelled": 0, "pending_payment": 0,
            "processing": 0, "last_30_days": last_30_days
        }
        
        for stat in status_stats:
            status_key = stat["_id"]
            if status_key in stats:
                stats[status_key] = stat["count"]
            stats["total"] += stat["count"]
        
        # Save to cache (5 minutes)
        await set_cached(cache_key, stats, ttl=300)
        
        return OrderStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi khi lấy thống kê")


# ==================== GET SINGLE ORDER ====================

@router.get("/{order_id}")
async def get_order(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    include_product_details: bool = Query(False)
):
    """Get order detail"""
    
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="ID đơn hàng không hợp lệ")
    
    try:
        order = await db["orders"].find_one(
            {"_id": ObjectId(order_id), "user_id": ObjectId(current_user.id)}
        )
        
        if not order:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
        
        order["_id"] = str(order["_id"])
        order["order_code"] = str(order["_id"])[-8:].upper()
        order["user_id"] = str(order["user_id"])
        
        for item in order.get("items", []):
            item["product_id"] = str(item["product_id"])
            if item.get("variant_id"):
                item["variant_id"] = str(item["variant_id"])
            if item.get("shop_id"):
                item["shop_id"] = str(item["shop_id"])
        
        # Add timeline
        order["timeline"] = await _get_order_timeline(db, order)
        
        return order
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi khi lấy chi tiết đơn hàng")


# ==================== OTHER ENDPOINTS ====================

@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    status_update: OrderUpdate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Update order status"""
    user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
    if not user or user.get("role") not in ["admin", "shop"]:
        raise HTTPException(status_code=403, detail="Không có quyền")
    
    service = OrderService(db)
    
    try:
        result = await service.update_order_status(order_id, status_update.status)
        await invalidate_cache(f"user_orders:{current_user.id}:*")
        await invalidate_cache(f"order_stats:{current_user.id}")
        
        return {"status": "success", "message": "Đã cập nhật trạng thái", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_id}/cancel", response_model=CancelOrderResponse)
async def cancel_order(
    order_id: str,
    cancel_reason: Optional[str] = Query(None),
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Cancel order"""
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="ID đơn hàng không hợp lệ")
    
    service = OrderService(db)
    
    try:
        result = await service.cancel_order(order_id, str(current_user.id), cancel_reason)
        await invalidate_cache(f"user_orders:{current_user.id}:*")
        await invalidate_cache(f"order_stats:{current_user.id}")
        
        return CancelOrderResponse(
            status="success",
            message="Đơn hàng đã được hủy",
            refund_amount=result.get("refund_amount")
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_id}/resend-email")
async def resend_order_email(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Resend order email"""
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="ID đơn hàng không hợp lệ")
    
    service = OrderService(db)
    order = await service.get_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    if order["user_id"] != str(current_user.id):
        user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
        if not user or user.get("role") not in ["admin"]:
            raise HTTPException(status_code=403, detail="Không có quyền")
    
    background_tasks = BackgroundTasks()
    background_tasks.add_task(
        service._send_customer_order_email,
        current_user.email,
        current_user.full_name or current_user.username,
        order_id,
        order_id[-8:].upper(),
        order
    )
    
    return {"status": "success", "message": "Email xác nhận đã được gửi lại"}


@router.get("/export/my")
async def export_my_orders(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    format: str = Query("json", pattern="^(json|csv)$"),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """Export orders"""
    from_date_parsed = parse_date(from_date) if 'parse_date' in dir() else None
    to_date_parsed = parse_date(to_date) if 'parse_date' in dir() else None
    
    query = {"user_id": ObjectId(current_user.id)}
    
    orders = []
    cursor = db["orders"].find(query).sort("created_at", -1)
    
    async for order in cursor:
        orders.append({
            "order_id": str(order["_id"]),
            "order_code": str(order["_id"])[-8:].upper(),
            "total_amount": order.get("total_amount", 0),
            "status": order.get("status"),
            "payment_status": order.get("payment_status"),
            "created_at": order.get("created_at").isoformat() if order.get("created_at") else None
        })
    
    if format == "csv":
        import csv
        from fastapi.responses import StreamingResponse
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["order_id", "order_code", "total_amount", "status", "payment_status", "created_at"])
        writer.writeheader()
        writer.writerows(orders)
        
        response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=orders.csv"
        return response
    
    return {"data": orders, "count": len(orders)}

# app/routes/order_router.py (thêm vào cuối file)

@router.get("/{order_id}/payment-status")
async def get_payment_status(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Check payment status of order (for polling)"""
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="ID đơn hàng không hợp lệ")
    
    try:
        order = await db["orders"].find_one(
            {"_id": ObjectId(order_id), "user_id": ObjectId(current_user.id)},
            {"payment_status": 1, "status": 1, "paid_at": 1}
        )
        
        if not order:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
        
        return {
            "payment_status": order.get("payment_status", "unpaid"),
            "status": order.get("status", "pending"),
            "paid_at": order.get("paid_at"),
            "order_id": order_id,
            "order_code": order_id[-8:].upper()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking payment status: {e}")
        raise HTTPException(status_code=500, detail="Lỗi khi kiểm tra trạng thái")
# ==================== HELPER FUNCTIONS ====================

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string safely"""
    if not date_str:
        return None
    try:
        if date_str.endswith('Z'):
            date_str = date_str.replace('Z', '+00:00')
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        logger.warning(f"Invalid date format: {date_str}")
        return None


async def _get_order_timeline(db, order: Dict) -> List[Dict]:
    """Generate order timeline"""
    timeline = []
    
    if order.get("created_at"):
        timeline.append({
            "status": "created",
            "title": "Đơn hàng được tạo",
            "timestamp": order["created_at"],
            "icon": "check_circle"
        })
    
    if order.get("payment_status") == "paid":
        timeline.append({
            "status": "paid",
            "title": "Đã thanh toán",
            "timestamp": order.get("paid_at") or order.get("updated_at"),
            "icon": "payment"
        })
    
    if order.get("status") == "shipped":
        timeline.append({
            "status": "shipped",
            "title": "Đang giao hàng",
            "timestamp": order.get("shipped_at") or order.get("updated_at"),
            "icon": "local_shipping"
        })
    
    if order.get("status") == "completed":
        timeline.append({
            "status": "completed",
            "title": "Giao hàng thành công",
            "timestamp": order.get("completed_at") or order.get("updated_at"),
            "icon": "check_circle"
        })
    
    if order.get("status") == "cancelled":
        timeline.append({
            "status": "cancelled",
            "title": "Đơn hàng bị hủy",
            "timestamp": order.get("cancelled_at") or order.get("updated_at"),
            "icon": "cancel"
        })
    
    return sorted(timeline, key=lambda x: x["timestamp"] or datetime.min, reverse=True)