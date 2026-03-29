from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from bson import ObjectId
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/shop/customers", tags=["Customers"])

@router.get("/")
async def get_customers(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None
):
    """
    Lấy danh sách khách hàng của shop (phân trang, tìm kiếm)
    """
    # Kiểm tra quyền
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy shop_id từ user
    shop_id = current_user.shop_id
    if not shop_id and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    # Tìm tất cả orders có chứa sản phẩm của shop này
    # SỬA: Tìm orders có items.shop_id = shop_id
    match_stage = {
        "$match": {
            "items.shop_id": ObjectId(shop_id) if current_user.role != "admin" else {"$exists": True}
        }
    }
    
    # Thêm điều kiện tìm kiếm
    if search:
        # Tìm user theo tên, email, phone
        users_with_search = await db["users"].find({
            "$or": [
                {"full_name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}},
                {"username": {"$regex": search, "$options": "i"}}
            ]
        }).to_list(length=None)
        
        user_ids = [u["_id"] for u in users_with_search]
        
        if user_ids:
            match_stage["$match"]["user_id"] = {"$in": user_ids}
    
    # Pipeline chính
    pipeline = [
        match_stage,
        {
            "$group": {
                "_id": "$user_id",
                "total_spent": {"$sum": "$total_amount"},  # SỬA: total_amount thay vì total_price
                "order_count": {"$sum": 1},
                "last_order": {"$max": "$created_at"},
                "orders": {"$push": {
                    "order_id": "$_id",
                    "total_amount": "$total_amount",
                    "status": "$status",
                    "created_at": "$created_at",
                    "items_count": {"$size": "$items"}
                }}
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "_id",
                "as": "user_info"
            }
        },
        {
            "$unwind": {
                "path": "$user_info",
                "preserveNullAndEmptyArrays": True
            }
        },
        {
            "$project": {
                "user_id": "$_id",
                "full_name": "$user_info.full_name",
                "username": "$user_info.username",
                "email": "$user_info.email",
                "phone": "$user_info.phone",
                "address": "$user_info.address",
                "gender": "$user_info.gender",
                "avatar_url": "$user_info.avatar_url",
                "total_spent": 1,
                "order_count": 1,
                "last_order": 1,
                "orders": 1,
                "created_at": "$user_info.created_at"
            }
        },
        {"$sort": {"last_order": -1}},
        {"$skip": (page - 1) * limit},
        {"$limit": limit}
    ]
    
    customers = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    # Đếm tổng số khách hàng
    count_pipeline = [
        match_stage,
        {"$group": {"_id": "$user_id"}},
        {"$count": "total"}
    ]
    count_result = await db["orders"].aggregate(count_pipeline).to_list(length=None)
    total = count_result[0]["total"] if count_result else 0
    
    # Format response
    result = []
    for c in customers:
        result.append({
            "id": str(c["user_id"]),
            "full_name": c.get("full_name") or c.get("username", ""),
            "username": c.get("username", ""),
            "email": c.get("email", ""),
            "phone": c.get("phone", ""),
            "address": c.get("address", ""),
            "gender": c.get("gender", ""),
            "avatar_url": c.get("avatar_url", ""),
            "total_spent": c.get("total_spent", 0),
            "order_count": c.get("order_count", 0),
            "last_order": c.get("last_order"),
            "created_at": c.get("created_at")
        })
    
    return {
        "data": result,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1
        }
    }


@router.get("/{customer_id}")
async def get_customer_detail(
    customer_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Xem chi tiết khách hàng (chỉ hiển thị đơn hàng từ shop của mình)
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy thông tin user
    user = await db["users"].find_one({"_id": ObjectId(customer_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng")
    
    # Lấy shop_id
    shop_id = current_user.shop_id
    
    # Lấy lịch sử mua hàng từ shop này
    query = {"user_id": ObjectId(customer_id)}
    if current_user.role != "admin" and shop_id:
        query["items.shop_id"] = ObjectId(shop_id)
    
    orders = await db["orders"].find(query).sort("created_at", -1).to_list(length=50)
    
    # Format orders
    formatted_orders = []
    total_spent = 0
    
    for order in orders:
        # Tính tổng tiền chỉ từ sản phẩm của shop này
        order_total_from_shop = 0
        items_count_from_shop = 0
        
        for item in order["items"]:
            if str(item["shop_id"]) == shop_id:
                order_total_from_shop += item["price"] * item["quantity"]
                items_count_from_shop += 1
        
        if order_total_from_shop > 0:
            formatted_orders.append({
                "id": str(order["_id"]),
                "total_price": order_total_from_shop,
                "status": order["status"],
                "created_at": order["created_at"],
                "items_count": items_count_from_shop
            })
            total_spent += order_total_from_shop
    
    # Tính tổng chi tiêu từ shop này
    total_spent = sum(o["total_price"] for o in formatted_orders)
    
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "address": user.get("address"),
        "gender": user.get("gender"),
        "dob": user.get("dob"),
        "avatar_url": user.get("avatar_url"),
        "total_spent": total_spent,
        "order_count": len(formatted_orders),
        "orders": formatted_orders,
        "created_at": user.get("created_at")
    }


@router.put("/{customer_id}")
async def update_customer(
    customer_id: str,
    data: dict,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Cập nhật thông tin khách hàng
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    # Chỉ cho phép update một số field
    allowed_fields = ["full_name", "phone", "address", "gender"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Không có dữ liệu để cập nhật")
    
    result = await db["users"].update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng")
    
    return {"message": "Cập nhật thành công"}


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Xóa khách hàng (admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền xóa")
    
    result = await db["users"].delete_one({"_id": ObjectId(customer_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng")
    
    return {"message": "Xóa khách hàng thành công"}


@router.get("/export/excel")
async def export_customers_excel(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Xuất danh sách khách hàng ra Excel
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy shop_id
    shop_id = current_user.shop_id
    
    # Pipeline để lấy danh sách khách hàng
    match_stage = {
        "$match": {
            "items.shop_id": ObjectId(shop_id) if current_user.role != "admin" else {"$exists": True}
        }
    }
    
    pipeline = [
        match_stage,
        {
            "$group": {
                "_id": "$user_id",
                "total_spent": {"$sum": "$total_amount"},
                "order_count": {"$sum": 1},
                "last_order": {"$max": "$created_at"}
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "_id",
                "as": "user_info"
            }
        },
        {
            "$unwind": {
                "path": "$user_info",
                "preserveNullAndEmptyArrays": True
            }
        }
    ]
    
    customers = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    # Format data for Excel
    excel_data = []
    for i, c in enumerate(customers, 1):
        user = c["user_info"]
        excel_data.append({
            "STT": i,
            "Tên khách hàng": user.get("full_name") or user.get("username", ""),
            "Số điện thoại": user.get("phone", ""),
            "Email": user.get("email", ""),
            "Địa chỉ": user.get("address", ""),
            "Tổng chi tiêu": c.get("total_spent", 0),
            "Số đơn hàng": c.get("order_count", 0),
            "Đơn gần nhất": c.get("last_order").strftime("%Y-%m-%d %H:%M") if c.get("last_order") else ""
        })
    
    return {
        "data": excel_data,
        "total": len(excel_data),
        "message": "Dữ liệu đã sẵn sàng để xuất Excel"
    }