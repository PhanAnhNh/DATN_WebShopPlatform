from fastapi import APIRouter, Depends
from app.db.mongodb import get_database
from app.services.share_services import PostShareService
from app.core.security import get_current_user

router = APIRouter(prefix="/shares", tags=["Shares"])

@router.post("/{post_id}")
async def share_post(
    post_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = PostShareService(db)
    return await service.share_post(post_id, str(current_user.id))


@router.get("/{post_id}")
async def get_post_shares(
    post_id: str,
    db = Depends(get_database)
):
    service = PostShareService(db)
    return await service.get_shares_by_post(post_id)