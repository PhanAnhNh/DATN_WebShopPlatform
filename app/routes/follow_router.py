from fastapi import APIRouter, Depends
from app.services.follow_service import FollowService
from app.db.mongodb import get_database
from app.core.security import CurrentUser, get_current_user

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

@router.get("/check/{user_id}")
async def check_follow_status(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Kiểm tra xem current user có đang follow user_id không
    """
    service = FollowService(db)
    is_following = await service.is_following(str(current_user.id), user_id)
    return {"isFollowing": is_following}