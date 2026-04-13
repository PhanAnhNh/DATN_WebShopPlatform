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
        # Tạo dict mới với các trường đã chuyển đổi
        order_dict = {
            "_id": str(order["_id"]),
            "user_id": str(order["user_id"]),
            "total_amount": order.get("total_amount", 0),
            "total_price": order.get("total_amount", 0),
            "subtotal": order.get("subtotal", 0),
            "discount": order.get("discount", 0),
            "shipping_fee": order.get("shipping_fee", 0),
            "status": order.get("status", "pending"),
            "payment_status": order.get("payment_status", "unpaid"),
            "payment_method": order.get("payment_method", "cod"),
            "shipping_address": order.get("shipping_address", ""),
            "shipping_address_details": order.get("shipping_address_details", {}),
            "note": order.get("note", ""),
            "created_at": order.get("created_at")
        }
        
        # Xử lý items
        items = []
        for idx, item in enumerate(order.get("items", [])):
            items.append({
                "_id": f"{order_dict['_id']}_item_{idx}",
                "product_id": str(item.get("product_id")),
                "shop_id": str(item.get("shop_id")),
                "quantity": item.get("quantity", 0),
                "price": item.get("price", 0),
                "variant_id": str(item.get("variant_id")) if item.get("variant_id") else None,
                "variant_name": item.get("variant_name", "")
            })
        order_dict["items"] = items
        
        # Xử lý voucher
        if order.get("voucher"):
            voucher = order["voucher"]
            order_dict["voucher"] = {
                "id": str(voucher.get("id")) if voucher.get("id") else None,
                "code": voucher.get("code", ""),
                "discount": voucher.get("discount", 0)
            }
        
        # Xử lý shipping unit
        if order.get("shipping_unit"):
            shipping_unit = order["shipping_unit"]
            order_dict["shipping_unit"] = {
                "id": shipping_unit.get("id"),
                "name": shipping_unit.get("name"),
                "code": shipping_unit.get("code"),
                "shipping_fee": shipping_unit.get("shipping_fee", 0),
                "estimated_delivery_days": shipping_unit.get("estimated_delivery_days", 3)
            }
        
        if order.get("shipping_unit_id"):
            order_dict["shipping_unit_id"] = str(order["shipping_unit_id"])
        
        # Thêm thông tin khách hàng
        try:
            user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
            if user:
                order_dict["customer_name"] = user.get("full_name", user.get("username", ""))
                order_dict["customer_phone"] = user.get("phone", "")
                order_dict["customer_email"] = user.get("email", "")
        except:
            order_dict["customer_name"] = ""
            order_dict["customer_phone"] = ""
            order_dict["customer_email"] = ""
        
        orders.append(order_dict)
    
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
    except Exception as e:
        print(f"Error finding order: {e}")
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    # Chuyển đổi ObjectId sang string cho tất cả các trường
    result = {}
    
    # Chuyển _id
    result["_id"] = str(order["_id"])
    result["order_id"] = str(order["_id"])
    result["user_id"] = str(order["user_id"])
    
    # Thêm total_price để tương thích với frontend
    result["total_price"] = order.get("total_amount", 0)
    result["total_amount"] = order.get("total_amount", 0)
    result["subtotal"] = order.get("subtotal", 0)
    result["discount"] = order.get("discount", 0)
    result["shipping_fee"] = order.get("shipping_fee", 0)
    result["status"] = order.get("status", "pending")
    result["payment_status"] = order.get("payment_status", "unpaid")
    result["payment_method"] = order.get("payment_method", "cod")
    result["shipping_address"] = order.get("shipping_address", "")
    result["shipping_address_details"] = order.get("shipping_address_details", {})
    result["note"] = order.get("note", "")
    result["created_at"] = order.get("created_at")
    
    # Xử lý items
    items = []
    for idx, item in enumerate(order.get("items", [])):
        item_result = {
            "_id": f"{result['_id']}_item_{idx}",
            "product_id": str(item.get("product_id")),
            "product_name": "",  # Sẽ lấy sau
            "shop_id": str(item.get("shop_id")),
            "quantity": item.get("quantity", 0),
            "price": item.get("price", 0),
            "variant_id": str(item.get("variant_id")) if item.get("variant_id") else None,
            "variant_name": item.get("variant_name", "")
        }
        
        # Lấy tên sản phẩm
        try:
            product = await db["products"].find_one({"_id": ObjectId(item["product_id"])})
            if product:
                item_result["product_name"] = product.get("name", "Sản phẩm")
            else:
                item_result["product_name"] = "Sản phẩm"
        except:
            item_result["product_name"] = "Sản phẩm"
        
        items.append(item_result)
    
    result["items"] = items
    
    # Xử lý voucher
    if order.get("voucher"):
        voucher = order["voucher"]
        result["voucher"] = {
            "id": str(voucher["id"]) if isinstance(voucher.get("id"), ObjectId) else voucher.get("id"),
            "code": voucher.get("code", ""),
            "discount": voucher.get("discount", 0)
        }
    
    # Xử lý shipping unit
    if order.get("shipping_unit"):
        shipping_unit = order["shipping_unit"]
        result["shipping_unit"] = {
            "id": shipping_unit.get("id"),
            "name": shipping_unit.get("name"),
            "code": shipping_unit.get("code"),
            "shipping_fee": shipping_unit.get("shipping_fee", 0),
            "estimated_delivery_days": shipping_unit.get("estimated_delivery_days", 3)
        }
    
    if order.get("shipping_unit_id"):
        result["shipping_unit_id"] = str(order["shipping_unit_id"])
    
    # Thêm customer info
    try:
        user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
        if user:
            result["customer_name"] = user.get("full_name", user.get("username", ""))
            result["customer_phone"] = user.get("phone", "")
            result["customer_email"] = user.get("email", "")
    except:
        result["customer_name"] = ""
        result["customer_phone"] = ""
        result["customer_email"] = ""
    
    return result

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
    
@router.post("/{order_id}/resend-email")
async def resend_order_email(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Gửi lại email xác nhận đơn hàng (nếu cần)"""
    service = OrderService(db)
    order = await service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Kiểm tra quyền
    if order["user_id"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Không có quyền")
    
    # Gửi lại email
    await service._send_customer_order_email(
        current_user.email,
        current_user.full_name or current_user.username,
        order_id,
        order_id[-8:].upper(),
        order
    )
    
    return {"message": "Email đã được gửi lại"}