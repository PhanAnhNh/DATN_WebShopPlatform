from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from bson import ObjectId
from typing import Optional, List
from datetime import datetime

router = APIRouter(prefix="/shop/customers", tags=["Customers"])

@router.get("/")
async def get_customers(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None
):
    """
    Lấy danh sách khách hàng của shop (phân trang, tìm kiếm)
    """
    # Kiểm tra quyền (chỉ shop_owner mới được xem)
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy shop_id từ user
    shop_id = current_user.shop_id
    if not shop_id and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    # Query filter
    filter_query = {}
    if current_user.role != "admin":
        # Nếu là shop_owner, chỉ lấy khách hàng của shop mình
        filter_query["shop_id"] = shop_id
    
    # Tìm kiếm theo tên, email, phone
    if search:
        filter_query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
        ]
    
    # Tính skip
    skip = (page - 1) * limit
    
    # Lấy danh sách khách hàng từ orders (distinct)
    pipeline = [
        {"$match": filter_query},
        {"$group": {
            "_id": "$user_id",
            "total_spent": {"$sum": "$total_price"},
            "order_count": {"$sum": 1},
            "last_order": {"$max": "$created_at"}
        }},
        {"$lookup": {
            "from": "users",
            "localField": "_id",
            "foreignField": "_id",
            "as": "user_info"
        }},
        {"$unwind": "$user_info"},
        {"$skip": skip},
        {"$limit": limit}
    ]
    
    customers = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    # Đếm tổng số
    count_pipeline = [
        {"$match": filter_query},
        {"$group": {"_id": "$user_id"}},
        {"$count": "total"}
    ]
    count_result = await db["orders"].aggregate(count_pipeline).to_list(length=None)
    total = count_result[0]["total"] if count_result else 0
    
    # Format response
    result = []
    for c in customers:
        user = c["user_info"]
        result.append({
            "id": str(user["_id"]),
            "full_name": user.get("full_name", user["username"]),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "address": user.get("address"),
            "total_spent": c.get("total_spent", 0),
            "order_count": c.get("order_count", 0),
            "last_order": c.get("last_order"),
            "created_at": user.get("created_at")
        })
    
    return {
        "data": result,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@router.get("/{customer_id}")
async def get_customer_detail(
    customer_id: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Xem chi tiết khách hàng
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy thông tin user
    user = await db["users"].find_one({"_id": ObjectId(customer_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng")
    
    # Lấy lịch sử mua hàng
    orders = await db["orders"].find(
        {"user_id": ObjectId(customer_id)}
    ).sort("created_at", -1).to_list(length=50)
    
    # Format orders
    formatted_orders = []
    for order in orders:
        formatted_orders.append({
            "id": str(order["_id"]),
            "total_price": order["total_price"],
            "status": order["status"],
            "created_at": order["created_at"],
            "items_count": len(order["items"])
        })
    
    # Tính tổng chi tiêu
    total_spent = sum(o["total_price"] for o in orders if o["status"] != "cancelled")
    
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
        "order_count": len(orders),
        "orders": formatted_orders,
        "created_at": user.get("created_at")
    }

@router.put("/{customer_id}")
async def update_customer(
    customer_id: str,
    data: dict,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
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
    current_user: UserInDB = Depends(get_current_user)
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
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Xuất danh sách khách hàng ra Excel
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy shop_id
    shop_id = current_user.shop_id
    
    # Query
    filter_query = {}
    if current_user.role != "admin":
        filter_query["shop_id"] = shop_id
    
    # Lấy danh sách khách hàng
    pipeline = [
        {"$match": filter_query},
        {"$group": {
            "_id": "$user_id",
            "total_spent": {"$sum": "$total_price"},
            "order_count": {"$sum": 1}
        }},
        {"$lookup": {
            "from": "users",
            "localField": "_id",
            "foreignField": "_id",
            "as": "user_info"
        }},
        {"$unwind": "$user_info"}
    ]
    
    customers = await db["orders"].aggregate(pipeline).to_list(length=None)
    
    # Format data for Excel
    excel_data = []
    for i, c in enumerate(customers, 1):
        user = c["user_info"]
        excel_data.append({
            "STT": i,
            "Tên khách hàng": user.get("full_name", user["username"]),
            "Số điện thoại": user.get("phone", ""),
            "Email": user.get("email", ""),
            "Địa chỉ": user.get("address", ""),
            "Tổng chi tiêu": c.get("total_spent", 0),
            "Số đơn hàng": c.get("order_count", 0)
        })
    
    # Trả về file Excel (cần thư viện xử lý Excel)
    # Ở đây tạm thời trả về JSON
    return {
        "data": excel_data,
        "total": len(excel_data),
        "message": "Dữ liệu đã sẵn sàng để xuất Excel"
    }