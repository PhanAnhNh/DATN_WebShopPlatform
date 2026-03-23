# app/routes/social_posts_routes.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from app.models.social_posts_model import (
    CategoryType,
    SocialPostCreate,
    SocialPostUpdate,
    SocialPostResponse
)
from app.services.social_posts_service import SocialPostService
from app.db.mongodb import get_database
from app.core.security import get_current_user, CurrentUser

router = APIRouter(prefix="/posts", tags=["Social Posts"])

# ĐẢM BẢO ENDPOINT NÀY ĐƯỢC ĐỊNH NGHĨA TRƯỚC CÁC ENDPOINT KHÁC
@router.get("/user/{user_id}", response_model=List[SocialPostResponse])
async def get_posts_by_user(
    user_id: str,
    limit: int = 10,
    skip: int = 0,
    db = Depends(get_database)
):
    """
    Lấy danh sách bài viết của một user cụ thể
    """
    print(f"=== GET /posts/user/{user_id} ===")  # Debug
    service = SocialPostService(db)
    try:
        posts = await service.get_user_posts(user_id=user_id, limit=limit, skip=skip)
        print(f"Found {len(posts)} posts for user {user_id}")  # Debug
        return posts
    except Exception as e:
        print(f"Error fetching posts for user {user_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Không tìm thấy bài viết cho user: {user_id}")

@router.get("/feed", response_model=List[SocialPostResponse])
async def get_social_feed(
    category: Optional[CategoryType] = None,
    limit: int = 10,
    skip: int = 0,
    db = Depends(get_database)
):
    service = SocialPostService(db)
    return await service.get_feed(limit, skip, category)

@router.get("/{post_id}", response_model=SocialPostResponse)
async def get_post_by_id(
    post_id: str,
    db = Depends(get_database)
):
    """Lấy bài viết theo ID"""
    service = SocialPostService(db)
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    return post

@router.post("/", response_model=SocialPostResponse)
async def create_new_post(
    post_in: SocialPostCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    service = SocialPostService(db)
    return await service.create_post(post_in, current_user)

@router.put("/{post_id}", response_model=SocialPostResponse)
async def update_my_post(
    post_id: str, 
    update_data: SocialPostUpdate, 
    current_user: CurrentUser = Depends(get_current_user), 
    db = Depends(get_database)
):
    service = SocialPostService(db)
    updated = await service.update_post(post_id, str(current_user.id), update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại hoặc bạn không có quyền sửa")
    return updated

@router.delete("/{post_id}")
async def delete_post(
    post_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    service = SocialPostService(db)
    deleted = await service.delete_post(post_id, str(current_user.id))
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Bài viết không tồn tại hoặc bạn không có quyền xóa"
        )
    return {"message": "Xóa bài viết thành công"}