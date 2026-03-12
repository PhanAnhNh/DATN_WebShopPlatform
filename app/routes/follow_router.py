from fastapi import APIRouter, Depends
from app.services.follow_service import FollowService
from app.db.mongodb import get_database
from app.core.security import get_current_user

router = APIRouter(prefix="/follows", tags=["Follows"])


@router.post("/{user_id}")
async def toggle_follow(
    user_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = FollowService(db)
    return await service.toggle_follow(str(current_user.id), user_id)

@router.get("/{user_id}/followers")
async def get_followers_list(
    user_id: str,
    db = Depends(get_database)
):
    service = FollowService(db)
    return await service.get_followers(user_id)

@router.get("/{user_id}/following")
async def get_following_list(
    user_id: str,
    db = Depends(get_database)
):
    service = FollowService(db)
    return await service.get_following(user_id)

@router.get("/{user_id}/stats")
async def get_follow_stats(
    user_id: str,
    db = Depends(get_database)
):
    service = FollowService(db)
    followers_count = await service.count_followers(user_id)
    following_count = await service.count_following(user_id)
    return {
        "followers_count": followers_count,
        "following_count": following_count
    }