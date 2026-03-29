# app/routes/return_router.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from typing import List, Optional
from bson import ObjectId
from app.db.mongodb import get_database
from app.core.security import get_current_shop_owner, get_current_user  # Xóa get_current_shop
from app.services.return_service import ReturnService
from app.services.notification_service import NotificationService
from app.models.return_model import ReturnCreate, ReturnUpdate, ReturnStatus
import os
import shutil
from datetime import datetime

router = APIRouter(prefix="/returns", tags=["Returns"])

# ============= USER ENDPOINTS =============

# app/routes/return_router.py
@router.post("/request")
async def create_return_request(
    return_data: ReturnCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Người dùng tạo yêu cầu đổi trả"""
    try:
        print("=" * 50)
        print("CREATE RETURN REQUEST")
        print(f"User ID: {current_user.id}")
        print(f"Order ID: {return_data.order_id}")
        print(f"Number of items: {len(return_data.items)}")
        
        for idx, item in enumerate(return_data.items):
            print(f"Item {idx}:")
            print(f"  - order_item_id: {item.order_item_id}")
            print(f"  - product_name: {item.product_name}")
            print(f"  - quantity: {item.quantity}")
            print(f"  - reason: {item.reason}")
        
        service = ReturnService(db)
        
        # Inject notification service
        notification_service = NotificationService(db)
        service.set_notification_service(notification_service)
        
        result, error = await service.create_return_request(
            user_id=str(current_user.id),
            return_data=return_data.model_dump()
        )
        
        if error:
            print(f"Error: {error}")
            raise HTTPException(status_code=400, detail=error)
        
        print(f"Success: Created return request {result.get('return_code')}")
        print("=" * 50)
        
        return {
            "message": "Yêu cầu đổi trả đã được gửi",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi server: {str(e)}")

# app/routes/return_router.py
@router.get("/my")
async def get_my_returns(
    db = Depends(get_database),
    current_user = Depends(get_current_user),
    order_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50)
):
    """Lấy danh sách yêu cầu đổi trả của người dùng"""
    service = ReturnService(db)
    
    # Nếu có order_id, lấy theo order
    if order_id:
        try:
            # Tìm yêu cầu hoàn trả theo order_id
            returns = await db["returns"].find({
                "order_id": ObjectId(order_id),
                "user_id": ObjectId(current_user.id)
            }).to_list(length=None)
            
            # Chuyển đổi ObjectId sang string
            result = []
            for ret in returns:
                ret["_id"] = str(ret["_id"])
                ret["user_id"] = str(ret["user_id"])
                ret["order_id"] = str(ret["order_id"])
                result.append(ret)
            
            return {"data": result}
        except Exception as e:
            print(f"Error in get_my_returns: {e}")
            return {"data": []}
    
    # Nếu không có order_id, lấy theo phân trang
    result = await service.get_my_returns(
        user_id=str(current_user.id),
        page=page,
        limit=limit
    )
    return result

@router.get("/my/{return_id}")
async def get_my_return_detail(
    return_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Xem chi tiết yêu cầu đổi trả của người dùng"""
    service = ReturnService(db)
    result = await service.get_return_detail(
        return_id=return_id,
        user_id=str(current_user.id)
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")
    
    return result

@router.get("/stats")
async def get_return_stats(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy thống kê đổi trả của người dùng"""
    service = ReturnService(db)
    stats = await service.get_return_stats(user_id=str(current_user.id))
    return stats

# ============= SHOP ENDPOINTS =============

@router.get("/shop")
async def get_shop_returns(
    db = Depends(get_database),
    current_shop_owner = Depends(get_current_shop_owner),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    status: Optional[str] = None,
    search: Optional[str] = None
):
    """Shop lấy danh sách yêu cầu đổi trả"""
    service = ReturnService(db)
    
    # Lấy shop_id từ current_shop_owner
    shop_id = current_shop_owner.shop_id
    
    result = await service.get_shop_returns(
        shop_id=shop_id,
        page=page,
        limit=limit,
        status=status,
        search=search
    )
    return result

@router.get("/shop/{return_id}")
async def get_shop_return_detail(
    return_id: str,
    db = Depends(get_database),
    current_shop_owner = Depends(get_current_shop_owner),
):
    """Shop xem chi tiết yêu cầu đổi trả"""
    service = ReturnService(db)
    result = await service.get_return_detail(return_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")
    
    # Kiểm tra quyền
    order = await db["orders"].find_one({"_id": ObjectId(result["order_id"])})
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    
    shop_in_order = False
    for item in order["items"]:
        if str(item["shop_id"]) == current_shop_owner.shop_id:
            shop_in_order = True
            break
    
    if not shop_in_order:
        raise HTTPException(status_code=403, detail="Không có quyền xem yêu cầu này")
    
    return result

@router.put("/shop/{return_id}/process")
async def process_return_request(
    return_id: str,
    update_data: ReturnUpdate,
    db = Depends(get_database),
    current_shop_owner = Depends(get_current_shop_owner),
):
    """Shop xử lý yêu cầu đổi trả"""
    service = ReturnService(db)
    
    # Inject notification service
    notification_service = NotificationService(db)
    service.set_notification_service(notification_service)
    
    result, error = await service.update_return_status(
        return_id=return_id,
        shop_id=current_shop_owner.shop_id,
        update_data=update_data.model_dump(exclude_none=True)
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")
    
    return {
        "message": "Đã cập nhật trạng thái yêu cầu",
        "data": result
    }

@router.get("/shop/stats")
async def get_shop_return_stats(
    db = Depends(get_database),
    current_shop_owner = Depends(get_current_shop_owner),
):
    """Lấy thống kê đổi trả cho shop"""
    service = ReturnService(db)
    stats = await service.get_return_stats(shop_id=current_shop_owner.shop_id)
    return stats

# ============= UPLOAD IMAGES =============

@router.post("/upload-image")
async def upload_return_image(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload ảnh chứng minh cho yêu cầu đổi trả"""
    # Kiểm tra file type
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file ảnh (JPEG, PNG)")
    
    # Tạo tên file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"return_{timestamp}_{file.filename}"
    
    # Lưu file
    upload_dir = "uploads/returns"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Trả về URL
    return {"url": f"/uploads/returns/{filename}"}