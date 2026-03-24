from fastapi import APIRouter, Depends, HTTPException
from typing import List
from bson import ObjectId

from app.services.friend_service import FriendService
from app.models.friend_model import FriendRequestCreate, FriendRequestUpdate
from app.db.mongodb import get_database
from app.core.security import get_current_user, CurrentUser

router = APIRouter(prefix="/friends", tags=["Friends"])

@router.post("/request")
async def send_friend_request(
    request_data: FriendRequestCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Gửi lời mời kết bạn"""
    service = FriendService(db)
    try:
        result = await service.send_friend_request(
            user_id=str(current_user.id),
            friend_id=request_data.friend_id
        )
        return {"message": "Đã gửi lời mời kết bạn", "request": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/request/{request_id}/accept")
async def accept_friend_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Chấp nhận lời mời kết bạn"""
    service = FriendService(db)
    success = await service.accept_friend_request(request_id, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy lời mời")
    return {"message": "Đã chấp nhận lời mời kết bạn"}

@router.put("/request/{request_id}/reject")
async def reject_friend_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Từ chối lời mời kết bạn"""
    service = FriendService(db)
    success = await service.reject_friend_request(request_id, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy lời mời")
    return {"message": "Đã từ chối lời mời"}

@router.get("/list")
async def get_friends(
    limit: int = 20,
    skip: int = 0,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Lấy danh sách bạn bè"""
    service = FriendService(db)
    friends = await service.get_friends(str(current_user.id), limit, skip)
    return friends

@router.get("/requests/pending")
async def get_pending_requests(
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Lấy danh sách lời mời kết bạn đang chờ"""
    service = FriendService(db)
    requests = await service.get_pending_requests(str(current_user.id))
    return requests

@router.get("/check/{user_id}")
async def check_friendship(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Kiểm tra quan hệ với user khác"""
    service = FriendService(db)
    status = await service.check_friendship(str(current_user.id), user_id)
    return status

@router.post("/block/{user_id}")
async def block_user(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Chặn người dùng"""
    service = FriendService(db)
    success = await service.block_user(str(current_user.id), user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Không thể chặn người dùng")
    return {"message": "Đã chặn người dùng"}

@router.delete("/{friend_id}")
async def unfriend(
    friend_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Hủy kết bạn"""
    service = FriendService(db)
    success = await service.unfriend(str(current_user.id), friend_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy bạn bè hoặc đã hủy kết bạn trước đó")
    return {"message": "Đã hủy kết bạn"}