from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from app.db.mongodb import get_database
from app.services.save_service import SaveService
from app.models.save_model import SavedPostCreate, SavedPostResponse, SavedPostWithDetails
from app.core.security import get_current_user

router = APIRouter(prefix="/saves", tags=["Saved Posts"], redirect_slashes=False)

def get_save_service(db=Depends(get_database)):
    return SaveService(db)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def save_post(
    data: SavedPostCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Lưu bài viết
    """
    service = SaveService(db)
    saved = await service.save_post(str(current_user.id), data)
    
    if not saved:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    
    return {
        "message": "Đã lưu bài viết",
        "saved": saved,
        "is_saved": True
    }


@router.delete("/{post_id}")
async def unsave_post(
    post_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Bỏ lưu bài viết
    """
    service = SaveService(db)
    success = await service.unsave_post(str(current_user.id), post_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Bài viết chưa được lưu")
    
    return {
        "message": "Đã bỏ lưu bài viết",
        "is_saved": False
    }


@router.get("/check/{post_id}")
async def check_saved(
    post_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Kiểm tra bài viết đã được lưu chưa
    """
    service = SaveService(db)
    is_saved = await service.check_saved(str(current_user.id), post_id)
    
    return {
        "post_id": post_id,
        "is_saved": is_saved
    }


@router.get("/my-posts")
async def get_my_saved_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """
    Lấy danh sách bài viết đã lưu của user hiện tại
    """
    service = SaveService(db)
    saved_posts = await service.get_saved_posts(str(current_user.id), skip, limit)
    
    return saved_posts


@router.get("/count/{post_id}")
async def get_saved_count(
    post_id: str,
    db = Depends(get_database)
):
    """
    Lấy số lượng người lưu bài viết
    """
    service = SaveService(db)
    count = await service.get_saved_count(post_id)
    
    return {
        "post_id": post_id,
        "saved_count": count
    }