# app/routes/social_posts_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from app.models.social_posts_model import (
    CategoryType,
    SocialPostCreate,
    SocialPostUpdate,
    SocialPostResponse
)
from app.services.social_posts_service import SocialPostService
from app.db.mongodb import get_database
from app.core.security import get_current_admin, get_current_user, CurrentUser, get_current_user_optional

router = APIRouter(prefix="/posts", tags=["Social Posts"])

@router.get("/search", response_model=List[SocialPostResponse])
async def search_posts(
    keyword: str = Query(..., min_length=1, description="Từ khóa tìm kiếm"),
    limit: int = Query(20, ge=1, le=50, description="Số lượng kết quả tối đa"),
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Tìm kiếm bài viết theo nội dung và tags
    """
    service = SocialPostService(db)
    results = await service.search_posts(
        keyword=keyword,
        limit=limit,
        current_user_id=str(current_user.id)
    )
    return results

@router.get("/feed", response_model=List[SocialPostResponse])
async def get_social_feed(
    category: Optional[CategoryType] = None,
    limit: int = 10,
    skip: int = 0,
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db = Depends(get_database)
):
    service = SocialPostService(db)
    user_id = str(current_user.id) if current_user else None
    result = await service.get_feed(
        limit=limit, 
        skip=skip, 
        category=category,
        current_user_id=user_id
    )
    
    # Debug log để kiểm tra shared_post
    for post in result:
        if post.get("post_type") == "share":
            print(f"Post ID: {post.get('_id')}, shared_post_id: {post.get('shared_post_id')}, has_shared_post: {post.get('shared_post') is not None}")
    
    return result

@router.get("/{post_id}", response_model=SocialPostResponse)
async def get_post_by_id(
    post_id: str,
    db = Depends(get_database),
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)  # có thể không cần đăng nhập
):
    service = SocialPostService(db)
    post = await service.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Bài viết không tồn tại")
    
    # Tăng view_count
    await service.increment_view_count(post_id)
    
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

@router.delete("/admin/{post_id}/permanent")
async def permanently_delete_post(
    post_id: str,
    current_user: CurrentUser = Depends(get_current_admin),
    db = Depends(get_database)
):
    """
    Admin xóa vĩnh viễn bài viết
    """
    service = SocialPostService(db)
    deleted = await service.delete_post_admin(post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    return {"message": "Đã xóa vĩnh viễn bài viết"}

@router.get("/user/{user_id}", response_model=List[SocialPostResponse])
async def get_user_posts_endpoint(
    user_id: str,
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0),
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db = Depends(get_database)
):
    service = SocialPostService(db)
    current_user_id = str(current_user.id) if current_user else None
    
    posts = await service.get_user_posts(
        user_id=user_id,
        limit=limit,
        skip=skip,
        current_user_id=current_user_id
    )
    return posts

