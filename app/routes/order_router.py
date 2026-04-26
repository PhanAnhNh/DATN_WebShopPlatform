# app/routes/orders_router.py
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from fastapi.responses import JSONResponse
from app.core.cache import cache_response, invalidate_cache
from app.db.mongodb import get_database

from app.models.orders_model import OrderCreate, OrderStatus, OrderUpdate
from app.core.security import get_current_user

from bson import ObjectId
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging
import asyncio

from app.services.order_service import OrderService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orders", tags=["Orders"])

# ==================== MODELS ====================

class OrderListResponse(BaseModel):
    """Response model for order list"""
    data: List[Dict[str, Any]]
    pagination: Dict[str, int]
    filters: Dict[str, Any]

class OrderStatsResponse(BaseModel):
    """Response model for order statistics"""
    total: int
    pending: int
    paid: int
    shipped: int
    completed: int
    cancelled: int
    pending_payment: int = Field(0, description="Chờ thanh toán")
    processing: int = Field(0, description="Đang xử lý")
    last_30_days: Optional[int] = Field(None, description="Đơn hàng 30 ngày qua")

class CancelOrderResponse(BaseModel):
    """Response model for cancel order"""
    status: str
    message: str
    refund_amount: Optional[float] = None

# ==================== HELPER FUNCTIONS ====================

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string safely"""
    if not date_str:
        return None
    try:
        # Handle ISO format with Z
        if date_str.endswith('Z'):
            date_str = date_str.replace('Z', '+00:00')
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        logger.warning(f"Invalid date format: {date_str}")
        return None

def build_order_query(
    user_id: str,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    search: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None
) -> Dict[str, Any]:
    """Build MongoDB query with all filters"""
    query = {"user_id": ObjectId(user_id)}
    
    # Status filter
    if status:
        query["status"] = status
    
    # Payment status filter
    if payment_status:
        query["payment_status"] = payment_status
    
    # Date range filter
    if from_date or to_date:
        date_filter = {}
        if from_date:
            date_filter["$gte"] = from_date
        if to_date:
            # Add one day to include the end date
            to_date_end = to_date + timedelta(days=1) if to_date else None
            date_filter["$lte"] = to_date_end or to_date
        if date_filter:
            query["created_at"] = date_filter
    
    # Amount range filter
    if min_amount is not None or max_amount is not None:
        amount_filter = {}
        if min_amount is not None:
            amount_filter["$gte"] = min_amount
        if max_amount is not None:
            amount_filter["$lte"] = max_amount
        if amount_filter:
            query["total_amount"] = amount_filter
    
    # Search by order ID or code
    if search:
        # Check if search is a valid ObjectId (24 hex chars)
        if len(search) == 24 and all(c in '0123456789abcdefABCDEF' for c in search):
            try:
                query["_id"] = ObjectId(search)
            except:
                pass
        else:
            # Search by order code (last 8 chars of ID)
            query["_id"] = {"$regex": f".*{search}.*", "$options": "i"}
    
    return query

# ==================== MAIN ENDPOINTS ====================

@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_order(
    order: OrderCreate,
    background_tasks: BackgroundTasks,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Tạo đơn hàng mới
    
    - **Tối ưu response time < 2 giây**
    - **Xử lý email và notification trong background**
    - **Tự động validate stock và cập nhật số lượng**
    """
    service = OrderService(db)
    
    try:
        # Validate order data before processing
        if not order.items:
            raise HTTPException(status_code=400, detail="Đơn hàng không có sản phẩm")
        
        if order.total_amount <= 0:
            raise HTTPException(status_code=400, detail="Tổng tiền đơn hàng không hợp lệ")
        
        # Create order (optimized for speed)
        result = await service.create_order(
            str(current_user.id),
            order.model_dump()
        )
        
        # Invalidate cache for user orders
        await invalidate_cache(f"user_orders:{current_user.id}:*")
        await invalidate_cache(f"order_stats:{current_user.id}")
        
        logger.info(f"✅ Order created successfully: {result.get('order_code')}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create order: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my", response_model=OrderListResponse)
@cache_response(ttl=30)  # Cache for 30 seconds
async def get_my_orders(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(10, ge=1, le=50, description="Số lượng mỗi trang"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái"),
    payment_status: Optional[str] = Query(None, description="Lọc theo trạng thái thanh toán"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo mã đơn"),
    from_date: Optional[str] = Query(None, description="Từ ngày (ISO format)"),
    to_date: Optional[str] = Query(None, description="Đến ngày (ISO format)"),
    min_amount: Optional[float] = Query(None, ge=0, description="Tối thiểu"),
    max_amount: Optional[float] = Query(None, ge=0, description="Tối đa"),
    sort_by: str = Query("created_at", description="Sắp xếp theo"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="ASC/DESC")
):
    """
    Lấy danh sách đơn hàng của user hiện tại với phân trang và filter
    
    - **Hỗ trợ cache để tăng tốc độ**
    - **Tối ưu query với indexing**
    - **Phân trang và filter linh hoạt**
    """
    # Parse dates
    from_date_parsed = parse_date(from_date)
    to_date_parsed = parse_date(to_date)
    
    # Build query
    query = build_order_query(
        user_id=str(current_user.id),
        status=status,
        payment_status=payment_status,
        from_date=from_date_parsed,
        to_date=to_date_parsed,
        search=search,
        min_amount=min_amount,
        max_amount=max_amount
    )
    
    # Validate sort field (prevent injection)
    allowed_sort_fields = ["created_at", "total_amount", "status", "updated_at"]
    if sort_by not in allowed_sort_fields:
        sort_by = "created_at"
    
    sort_direction = -1 if sort_order == "desc" else 1
    
    try:
        # Get total count (using estimated count for large collections)
        if page == 1 and not any([status, payment_status, search, from_date, to_date]):
            # Use estimated count for better performance on first page without filters
            total = await db["orders"].estimated_document_count()
        else:
            total = await db["orders"].count_documents(query)
        
        if total == 0:
            return OrderListResponse(
                data=[],
                pagination={"page": page, "limit": limit, "total": 0, "total_pages": 0},
                filters={"status": status, "payment_status": payment_status}
            )
        
        # Calculate pagination
        skip = (page - 1) * limit
        total_pages = (total + limit - 1) // limit
        
        # Fetch orders with projection (only needed fields)
        cursor = db["orders"].find(
            query,
            {
                # Project only needed fields for list view
                "_id": 1, "user_id": 1, "total_amount": 1, "status": 1,
                "payment_status": 1, "payment_method": 1, "created_at": 1,
                "items": {"$slice": 2},  # Only first 2 items for preview
                "subtotal": 1, "discount": 1, "shipping_fee": 1
            }
        ).sort(sort_by, sort_direction).skip(skip).limit(limit)
        
        # Process orders
        orders = []
        async for order in cursor:
            # Convert ObjectId to string
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
                        "product_name": item.get("variant_name") or "Sản phẩm",
                        "quantity": item.get("quantity", 0),
                        "price": item.get("price", 0)
                    }
                    for item in order.get("items", [])[:2]
                ]
            }
            orders.append(order_dict)
        
        return OrderListResponse(
            data=orders,
            pagination={
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages
            },
            filters={
                "status": status,
                "payment_status": payment_status,
                "from_date": from_date,
                "to_date": to_date,
                "min_amount": min_amount,
                "max_amount": max_amount
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching orders: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi khi lấy danh sách đơn hàng")


@router.get("/stats", response_model=OrderStatsResponse)
@cache_response(ttl=300)  # Cache for 5 minutes
async def get_order_stats(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="Số ngày gần nhất")
):
    """
    Lấy thống kê đơn hàng của user
    
    - **Cache 5 phút**
    - **Thống kê chi tiết theo trạng thái**
    - **Đơn hàng trong N ngày gần nhất**
    """
    user_id = ObjectId(current_user.id)
    
    # Calculate date range for last N days
    days_ago = datetime.utcnow() - timedelta(days=days)
    
    try:
        # Use aggregation pipeline for better performance
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        status_stats = await db["orders"].aggregate(pipeline).to_list(length=None)
        
        # Get orders in last N days
        recent_pipeline = [
            {"$match": {
                "user_id": user_id,
                "created_at": {"$gte": days_ago}
            }},
            {"$count": "total"}
        ]
        
        recent_result = await db["orders"].aggregate(recent_pipeline).to_list(length=None)
        last_30_days = recent_result[0]["total"] if recent_result else 0
        
        # Initialize stats
        stats = {
            "total": 0,
            "pending": 0,
            "paid": 0,
            "shipped": 0,
            "completed": 0,
            "cancelled": 0,
            "pending_payment": 0,
            "processing": 0,
            "last_30_days": last_30_days
        }
        
        # Map status to stats
        status_mapping = {
            "pending": "pending",
            "paid": "paid",
            "shipped": "shipped",
            "completed": "completed",
            "cancelled": "cancelled",
            "pending_payment": "pending_payment",
            "processing": "processing"
        }
        
        for stat in status_stats:
            status_key = status_mapping.get(stat["_id"], stat["_id"])
            if status_key in stats:
                stats[status_key] = stat["count"]
            stats["total"] += stat["count"]
        
        return OrderStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Error getting order stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi khi lấy thống kê đơn hàng")


@router.get("/{order_id}")
@cache_response(ttl=60)  # Cache for 1 minute
async def get_order(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    include_product_details: bool = Query(False, description="Include full product details")
):
    """
    Lấy chi tiết đơn hàng của user hiện tại
    
    - **Cache 1 phút**
    - **Tùy chọn lấy thêm chi tiết sản phẩm**
    """
    # Validate order_id format
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="ID đơn hàng không hợp lệ")
    
    try:
        # Fetch order with projection
        projection = {
            "_id": 1, "user_id": 1, "total_amount": 1, "subtotal": 1,
            "discount": 1, "shipping_fee": 1, "status": 1, "payment_status": 1,
            "payment_method": 1, "shipping_address": 1, "shipping_address_details": 1,
            "note": 1, "created_at": 1, "items": 1, "voucher": 1,
            "shipping_unit": 1, "shipping_unit_id": 1, "tracking_code": 1
        }
        
        order = await db["orders"].find_one(
            {"_id": ObjectId(order_id), "user_id": ObjectId(current_user.id)},
            projection
        )
        
        if not order:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
        
        # Build response
        result = {
            "_id": str(order["_id"]),
            "order_id": str(order["_id"]),
            "order_code": str(order["_id"])[-8:].upper(),
            "user_id": str(order["user_id"]),
            "total_amount": order.get("total_amount", 0),
            "subtotal": order.get("subtotal", 0),
            "discount": order.get("discount", 0),
            "shipping_fee": order.get("shipping_fee", 0),
            "status": order.get("status", "pending"),
            "payment_status": order.get("payment_status", "unpaid"),
            "payment_method": order.get("payment_method", "cod"),
            "shipping_address": order.get("shipping_address", ""),
            "shipping_address_details": order.get("shipping_address_details", {}),
            "note": order.get("note", ""),
            "created_at": order.get("created_at"),
            "tracking_code": order.get("tracking_code"),
            "estimated_delivery": None
        }
        
        # Add estimated delivery date
        if order.get("shipping_unit", {}).get("estimated_delivery_days"):
            days = order["shipping_unit"]["estimated_delivery_days"]
            result["estimated_delivery"] = order["created_at"] + timedelta(days=days)
        
        # Process items
        items = []
        for idx, item in enumerate(order.get("items", [])):
            item_result = {
                "_id": f"{result['_id']}_item_{idx}",
                "product_id": str(item.get("product_id")),
                "shop_id": str(item.get("shop_id")),
                "quantity": item.get("quantity", 0),
                "price": item.get("price", 0),
                "variant_id": str(item.get("variant_id")) if item.get("variant_id") else None,
                "variant_name": item.get("variant_name", ""),
                "total": item.get("price", 0) * item.get("quantity", 0)
            }
            
            # Include full product details if requested
            if include_product_details:
                try:
                    product = await db["products"].find_one(
                        {"_id": ObjectId(item["product_id"])},
                        {"name": 1, "images": 1, "sku": 1}
                    )
                    if product:
                        item_result["product_name"] = product.get("name", "Sản phẩm")
                        item_result["product_image"] = product.get("images", [None])[0] if product.get("images") else None
                        item_result["product_sku"] = product.get("sku")
                    else:
                        item_result["product_name"] = "Sản phẩm"
                except:
                    item_result["product_name"] = "Sản phẩm"
            else:
                item_result["product_name"] = item.get("variant_name") or "Sản phẩm"
            
            items.append(item_result)
        
        result["items"] = items
        result["item_count"] = len(items)
        
        # Process voucher
        if order.get("voucher"):
            voucher = order["voucher"]
            result["voucher"] = {
                "id": str(voucher.get("id")) if isinstance(voucher.get("id"), ObjectId) else voucher.get("id"),
                "code": voucher.get("code", ""),
                "discount": voucher.get("discount", 0),
                "discount_type": voucher.get("type", "fixed")
            }
        
        # Process shipping unit
        if order.get("shipping_unit"):
            result["shipping_unit"] = order["shipping_unit"]
        
        if order.get("shipping_unit_id"):
            result["shipping_unit_id"] = str(order["shipping_unit_id"])
        
        # Get customer info (from user collection)
        try:
            user = await db["users"].find_one(
                {"_id": ObjectId(current_user.id)},
                {"full_name": 1, "username": 1, "phone": 1, "email": 1}
            )
            if user:
                result["customer_name"] = user.get("full_name") or user.get("username", "")
                result["customer_phone"] = user.get("phone", "")
                result["customer_email"] = user.get("email", "")
        except:
            result["customer_name"] = ""
            result["customer_phone"] = ""
            result["customer_email"] = ""
        
        # Add timeline
        result["timeline"] = await _get_order_timeline(db, order)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order {order_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi khi lấy chi tiết đơn hàng")


@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    status_update: OrderUpdate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Cập nhật trạng thái đơn hàng (Admin/Shop only)
    """
    # Check if user has permission (admin or shop owner)
    user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
    if not user or user.get("role") not in ["admin", "shop"]:
        raise HTTPException(status_code=403, detail="Không có quyền cập nhật đơn hàng")
    
    service = OrderService(db)
    
    try:
        result = await service.update_order_status(order_id, status_update.status)
        
        # Invalidate cache
        await invalidate_cache(f"order:{order_id}")
        await invalidate_cache(f"user_orders:{current_user.id}:*")
        await invalidate_cache(f"order_stats:{current_user.id}")
        
        return {
            "status": "success",
            "message": f"Đã cập nhật trạng thái đơn hàng thành {status_update.status.value}",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_id}/cancel", response_model=CancelOrderResponse)
async def cancel_order(
    order_id: str,
    cancel_reason: Optional[str] = Query(None, description="Lý do hủy"),
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Hủy đơn hàng
    
    - **Hoàn lại số lượng sản phẩm trong kho**
    - **Cập nhật trạng thái đơn hàng**
    - **Gửi thông báo hủy**
    """
    # Validate order_id
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="ID đơn hàng không hợp lệ")
    
    service = OrderService(db)
    
    try:
        result = await service.cancel_order(order_id, str(current_user.id), cancel_reason)
        
        # Invalidate cache
        await invalidate_cache(f"order:{order_id}")
        await invalidate_cache(f"user_orders:{current_user.id}:*")
        await invalidate_cache(f"order_stats:{current_user.id}")
        
        return CancelOrderResponse(
            status="success",
            message="Đơn hàng đã được hủy thành công",
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
    """
    Gửi lại email xác nhận đơn hàng
    """
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="ID đơn hàng không hợp lệ")
    
    service = OrderService(db)
    order = await service.get_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    # Check permission
    if order["user_id"] != str(current_user.id):
        user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
        if not user or user.get("role") not in ["admin"]:
            raise HTTPException(status_code=403, detail="Không có quyền")
    
    # Send email in background
    background_tasks = BackgroundTasks()
    background_tasks.add_task(
        service._send_customer_order_email,
        current_user.email,
        current_user.full_name or current_user.username,
        order_id,
        order_id[-8:].upper(),
        order
    )
    
    return {
        "status": "success",
        "message": "Email xác nhận đã được gửi lại"
    }


@router.get("/export/my")
async def export_my_orders(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    format: str = Query("json", regex="^(json|csv)$"),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """
    Xuất danh sách đơn hàng của user (JSON hoặc CSV)
    """
    from_date_parsed = parse_date(from_date)
    to_date_parsed = parse_date(to_date)
    
    query = build_order_query(
        user_id=str(current_user.id),
        from_date=from_date_parsed,
        to_date=to_date_parsed
    )
    
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
        
        response = StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv"
        )
        response.headers["Content-Disposition"] = "attachment; filename=orders.csv"
        return response
    
    return {"data": orders, "count": len(orders)}


# ==================== HELPER FUNCTIONS ====================

async def _get_order_timeline(db, order: Dict) -> List[Dict]:
    """Generate order timeline"""
    timeline = []
    
    # Order created
    if order.get("created_at"):
        timeline.append({
            "status": "created",
            "title": "Đơn hàng được tạo",
            "description": "Đơn hàng đã được đặt thành công",
            "timestamp": order["created_at"],
            "icon": "check_circle"
        })
    
    # Payment confirmed (if paid)
    if order.get("payment_status") == "paid":
        timeline.append({
            "status": "paid",
            "title": "Đã thanh toán",
            "description": "Đơn hàng đã được thanh toán",
            "timestamp": order.get("paid_at") or order.get("updated_at"),
            "icon": "payment"
        })
    
    # Shipped
    if order.get("status") == "shipped":
        timeline.append({
            "status": "shipped",
            "title": "Đang giao hàng",
            "description": f"Đơn hàng đã được giao cho {order.get('shipping_unit', {}).get('name', 'đơn vị vận chuyển')}",
            "timestamp": order.get("shipped_at") or order.get("updated_at"),
            "icon": "local_shipping"
        })
    
    # Completed
    if order.get("status") == "completed":
        timeline.append({
            "status": "completed",
            "title": "Giao hàng thành công",
            "description": "Đơn hàng đã được giao thành công",
            "timestamp": order.get("completed_at") or order.get("updated_at"),
            "icon": "check_circle"
        })
    
    # Cancelled
    if order.get("status") == "cancelled":
        timeline.append({
            "status": "cancelled",
            "title": "Đơn hàng bị hủy",
            "description": order.get("cancel_reason", "Đơn hàng đã bị hủy"),
            "timestamp": order.get("cancelled_at") or order.get("updated_at"),
            "icon": "cancel"
        })
    
    return sorted(timeline, key=lambda x: x["timestamp"] or datetime.min, reverse=True)