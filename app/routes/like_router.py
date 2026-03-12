from fastapi import APIRouter, Depends
from app.db.mongodb import get_database
from app.services.like_services import PostLikeService
from app.core.security import get_current_user

router = APIRouter(prefix="/likes", tags=["Likes"])

@router.post("/{post_id}")
async def toggle_like(
    post_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = PostLikeService(db)
    return await service.toggle_like(post_id, str(current_user.id))

@router.get("/{post_id}")
async def get_post_likes(
    post_id: str,
    db = Depends(get_database)
):
    service = PostLikeService(db)
    return await service.get_likes_by_post(post_id)

@router.get("/check/{post_id}")
async def check_liked(
    post_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = PostLikeService(db)
    return {
        "liked": await service.is_liked(post_id, str(current_user.id))
    }