# app/routes/admin_posts_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.db.mongodb import get_database
from app.services.social_posts_service import SocialPostService
from app.core.security import get_current_user
from app.models.social_posts_model import SocialPostResponse, SocialPostUpdate

router = APIRouter(prefix="/admin/posts", tags=["Admin Posts"])

def get_post_service(db = Depends(get_database)):
    return SocialPostService(db)

@router.get("/", response_model=List[SocialPostResponse])
async def admin_get_all_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    visibility: Optional[str] = None,
    post_type: Optional[str] = None,
    service: SocialPostService = Depends(get_post_service),
    current_user = Depends(get_current_user)  # Yêu cầu đăng nhập
):
    """Admin lấy tất cả bài viết (có filter)"""
    # Kiểm tra quyền admin
    if getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Xây dựng filter
    filter_query = {}
    if visibility:
        filter_query["visibility"] = visibility
    if post_type:
        filter_query["post_type"] = post_type
    
    return await service.get_all_posts_admin(filter_query, skip, limit)

@router.put("/{post_id}/status")
async def admin_toggle_post_status(
    post_id: str,
    is_active: bool,
    service: SocialPostService = Depends(get_post_service),
    current_user = Depends(get_current_user)
):
    """Admin ẩn/hiện bài viết"""
    if getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    result = await service.update_post_admin(post_id, {"is_active": is_active})
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    
    return {"message": "Cập nhật trạng thái thành công"}

@router.delete("/{post_id}")
async def admin_delete_post(
    post_id: str,
    service: SocialPostService = Depends(get_post_service),
    current_user = Depends(get_current_user)
):
    """Admin xóa bài viết"""
    if getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    result = await service.delete_post_admin(post_id)
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    
    return {"message": "Xóa bài viết thành công"}

@router.put("/{post_id}")
async def admin_update_post(
    post_id: str,
    update_data: SocialPostUpdate,
    service: SocialPostService = Depends(get_post_service),
    current_user = Depends(get_current_user)
):
    """Admin cập nhật bài viết"""
    if getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy kết quả đã được convert từ service
    updated_post = await service.update_post_admin(post_id, update_data.dict(exclude_unset=True))
    
    if not updated_post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    
    return updated_post