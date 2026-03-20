# app/routes/shop_returns_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from app.models.return_model import ReturnStatus, ReturnUpdate
from app.services.return_service import ReturnService
from bson import ObjectId
from typing import Optional

router = APIRouter(prefix="/shop/returns", tags=["Shop Returns"])

@router.get("/")
async def get_shop_returns(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None
):
    """
    Lấy danh sách yêu cầu đổi trả của shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    service = ReturnService(db)
    
    result = await service.get_shop_returns(
        shop_id=current_user.shop_id,
        page=page,
        limit=limit,
        status=status,
        search=search
    )
    
    return result

@router.get("/stats")
async def get_return_stats(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thống kê đổi trả
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    service = ReturnService(db)
    
    stats = await service.get_return_stats(current_user.shop_id)
    
    return stats

@router.get("/{return_id}")
async def get_return_detail(
    return_id: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Xem chi tiết yêu cầu đổi trả
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    service = ReturnService(db)
    
    ret = await service.get_return_detail(return_id, current_user.shop_id)
    
    if not ret:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu")
    
    return ret

@router.put("/{return_id}/status")
async def update_return_status(
    return_id: str,
    update_data: ReturnUpdate,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Cập nhật trạng thái yêu cầu đổi trả
    """
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    service = ReturnService(db)
    
    ret, error = await service.update_return_status(
        return_id=return_id,
        shop_id=current_user.shop_id,
        update_data=update_data.dict(exclude_unset=True)
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    return ret