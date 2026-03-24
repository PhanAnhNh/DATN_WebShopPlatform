from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from app.models.orders_model import OrderStatus, StatusUpdateRequest
from bson import ObjectId
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter(prefix="/shop/orders", tags=["Shop Orders"])

class PaymentStatusUpdateRequest(BaseModel):
    payment_status: str  # 'paid' hoặc 'unpaid'

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
        try:
            date_filter["$gte"] = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        except:
            pass
    if to_date:
        try:
            date_filter["$lte"] = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        except:
            pass
    if date_filter:
        match_query["created_at"] = date_filter
    
    # Tìm kiếm theo tên khách hàng hoặc mã đơn
    if search:
        # Tìm user theo tên
        users = await db["users"].find({
            "$or": [
                {"full_name": {"$regex": search, "$options": "i"}},
                {"username": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}}
            ]
        }).to_list(length=None)
        
        if users:
            user_ids = [ObjectId(u["_id"]) for u in users]
            match_query["user_id"] = {"$in": user_ids}
    
    # Đếm tổng số đơn hàng
    count_pipeline = [
        {"$match": match_query},
        {"$count": "total"}
    ]
    count_result = await db["orders"].aggregate(count_pipeline).to_list(length=None)
    total = count_result[0]["total"] if count_result else 0
    
    # Lấy đơn hàng với pagination
    cursor = db["orders"].find(match_query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)
    
    orders = []
    async for order in cursor:
        # Lọc items thuộc shop này
        shop_items = []
        for item in order.get("items", []):
            if str(item.get("shop_id")) == current_user.shop_id:
                # Lấy thông tin sản phẩm
                product = await db["products"].find_one({"_id": item["product_id"]})
                product_name = product.get("name", "Sản phẩm") if product else "Sản phẩm"
                
                shop_items.append({
                    "product_id": str(item["product_id"]),
                    "product_name": product_name,
                    "variant_id": str(item["variant_id"]) if item.get("variant_id") else None,
                    "variant_name": item.get("variant_name", ""),
                    "quantity": item["quantity"],
                    "price": item["price"]
                })
        
        # Lấy thông tin user
        user_info = await db["users"].find_one({"_id": order["user_id"]})
        
        orders.append({
            "_id": str(order["_id"]),
            "order_id": str(order["_id"]),
            "customer_name": user_info.get("full_name", user_info.get("username", "")) if user_info else "",
            "customer_username": user_info.get("username", "") if user_info else "",
            "customer_phone": user_info.get("phone", "") if user_info else "",
            "customer_email": user_info.get("email", "") if user_info else "",
            "shipping_address": order.get("shipping_address", ""),
            "shipping_address_details": order.get("shipping_address_details", {}),
            "total_price": order.get("total_amount", order.get("total_price", 0)),
            "subtotal": order.get("subtotal", 0),
            "discount": order.get("discount", 0),  # THÊM DISCOUNT
            "shipping_fee": order.get("shipping_fee", 0),  # THÊM SHIPPING FEE
            "status": order.get("status", "pending"),
            "payment_status": order.get("payment_status", "unpaid"),
            "payment_method": order.get("payment_method", "cod"),
            "created_at": order.get("created_at"),
            "items": shop_items
        })
        
        # Thêm voucher nếu có
        if order.get("voucher"):
            orders[-1]["voucher"] = {
                "id": str(order["voucher"]["id"]) if isinstance(order["voucher"].get("id"), ObjectId) else order["voucher"].get("id"),
                "code": order["voucher"].get("code"),
                "discount": order["voucher"].get("discount", 0)
            }
    
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
    stats = {
        "pending": 0,
        "paid": 0,
        "shipped": 0,
        "completed": 0,
        "cancelled": 0,
        "total": 0,
        "today_revenue": 0
    }
    
    # Lấy tất cả đơn hàng có chứa sản phẩm của shop
    cursor = db["orders"].find({"items.shop_id": shop_id})
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_revenue = 0
    
    async for order in cursor:
        status = order.get("status", "pending")
        if status in stats:
            stats[status] += 1
        stats["total"] += 1
        
        # Tính doanh thu hôm nay
        if status in ["paid", "shipped", "completed"]:
            created_at = order.get("created_at")
            if created_at and created_at >= today_start:
                # Tính doanh thu từ các items của shop
                for item in order.get("items", []):
                    if str(item.get("shop_id")) == current_user.shop_id:
                        today_revenue += item["price"] * item["quantity"]
    
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
    
    try:
        order = await db["orders"].find_one({"_id": ObjectId(order_id)})
    except:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    # Lọc items thuộc shop này
    shop_items = []
    for item in order.get("items", []):
        if str(item.get("shop_id")) == current_user.shop_id:
            # Lấy thông tin sản phẩm
            product = await db["products"].find_one({"_id": item["product_id"]})
            product_name = product.get("name", "Sản phẩm") if product else "Sản phẩm"
            
            # Lấy thông tin variant
            variant_name = item.get("variant_name", "")
            if item.get("variant_id") and not variant_name:
                variant = await db["product_variants"].find_one({"_id": item["variant_id"]})
                if variant:
                    variant_name = variant.get("name", "")
            
            shop_items.append({
                "product_id": str(item["product_id"]),
                "product_name": product_name,
                "variant_id": str(item["variant_id"]) if item.get("variant_id") else None,
                "variant_name": variant_name,
                "quantity": item["quantity"],
                "price": item["price"]
            })
    
    # Lấy thông tin user
    user_info = await db["users"].find_one({"_id": order["user_id"]})
    
    # THÊM CÁC TRƯỜNG: discount, shipping_fee, voucher
    result = {
        "_id": str(order["_id"]),
        "order_id": str(order["_id"]),
        "user_id": str(order["user_id"]),
        "customer_name": user_info.get("full_name", user_info.get("username", "")) if user_info else "",
        "customer_username": user_info.get("username", "") if user_info else "",
        "customer_phone": user_info.get("phone", "") if user_info else "",
        "customer_email": user_info.get("email", "") if user_info else "",
        "shipping_address": order.get("shipping_address", ""),
        "shipping_address_details": order.get("shipping_address_details", {}),  # Thêm địa chỉ chi tiết
        "total_price": order.get("total_amount", order.get("total_price", 0)),
        "subtotal": order.get("subtotal", 0),  # Thêm subtotal
        "discount": order.get("discount", 0),  # THÊM DISCOUNT
        "shipping_fee": order.get("shipping_fee", 0),  # THÊM SHIPPING FEE
        "status": order.get("status", "pending"),
        "payment_status": order.get("payment_status", "unpaid"),
        "payment_method": order.get("payment_method", "cod"),  # Thêm payment_method
        "created_at": order.get("created_at"),
        "note": order.get("note", ""),  # Thêm note
        "items": shop_items
    }
    
    # THÊM VOUCHER NẾU CÓ
    if order.get("voucher"):
        voucher = order["voucher"]
        result["voucher"] = {
            "id": str(voucher["id"]) if isinstance(voucher.get("id"), ObjectId) else voucher.get("id"),
            "code": voucher.get("code"),
            "discount": voucher.get("discount", 0)
        }
    
    return result

@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    request: StatusUpdateRequest, 
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
    new_status = request.status  # Lấy status từ request body
    
    # Kiểm tra đơn hàng có chứa sản phẩm của shop không
    try:
        order = await db["orders"].find_one({
            "_id": ObjectId(order_id),
            "items.shop_id": shop_id
        })
    except:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    # Kiểm tra trạng thái hiện tại
    current_status = order.get("status")
    
    # Không cho phép cập nhật nếu đã hủy hoặc hoàn thành
    if current_status in ["cancelled", "completed"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Không thể cập nhật đơn hàng đã {current_status == 'cancelled' and 'hủy' or 'hoàn thành'}"
        )
    
    # Cập nhật trạng thái
    result = await db["orders"].update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": new_status.value}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Không thể cập nhật trạng thái")
    
    # Nếu đơn hàng hoàn thành, cập nhật doanh thu shop
    if new_status == OrderStatus.completed:
        # Tính doanh thu từ các sản phẩm của shop
        shop_revenue = 0
        for item in order.get("items", []):
            if str(item.get("shop_id")) == current_user.shop_id:
                shop_revenue += item.get("price", 0) * item.get("quantity", 0)
        
        await db["shops"].update_one(
            {"_id": shop_id},
            {
                "$inc": {
                    "total_revenue": shop_revenue,
                    "total_orders": 1
                }
            }
        )
    
    return {"message": "Cập nhật trạng thái thành công", "status": new_status.value}

@router.put("/{order_id}/payment-status")
async def update_payment_status(
    order_id: str,
    request: PaymentStatusUpdateRequest,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Cập nhật trạng thái thanh toán đơn hàng
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    shop_id = ObjectId(current_user.shop_id)
    new_payment_status = request.payment_status
    
    # Kiểm tra đơn hàng có chứa sản phẩm của shop không
    try:
        order = await db["orders"].find_one({
            "_id": ObjectId(order_id),
            "items.shop_id": shop_id
        })
    except:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    # Cập nhật trạng thái thanh toán
    result = await db["orders"].update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"payment_status": new_payment_status}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Không thể cập nhật trạng thái thanh toán")
    
    return {
        "message": "Cập nhật trạng thái thanh toán thành công",
        "order_id": order_id,
        "payment_status": new_payment_status
    }