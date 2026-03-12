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
from app.core.security import get_current_user

router = APIRouter(prefix="/posts", tags=["Social Posts"])

@router.get("/user/{user_id}", response_model=List[SocialPostResponse])
async def get_posts_by_user(
    user_id: str,
    limit: int = 10,
    skip: int = 0,
    db = Depends(get_database)
):
    service = SocialPostService(db)
    # Gọi hàm lấy bài viết theo user_id
    posts = await service.get_user_posts(user_id=user_id, limit=limit, skip=skip)
    return posts

@router.post("/", response_model=SocialPostResponse)
async def create_new_post(
    post_in: SocialPostCreate,
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    service = SocialPostService(db)
    return await service.create_post(post_in, current_user)


@router.get("/feed", response_model=List[SocialPostResponse])
async def get_social_feed(
    category: Optional[CategoryType] = None, # Thêm lọc theo category
    limit: int = 10,
    skip: int = 0,
    db = Depends(get_database)
):
    service = SocialPostService(db)
    return await service.get_feed(limit, skip, category)

@router.put("/{post_id}", response_model=SocialPostResponse)
async def update_my_post(
    post_id: str, 
    update_data: SocialPostUpdate, 
    current_user = Depends(get_current_user), 
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
    current_user = Depends(get_current_user),
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