from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.models.message_model import MessageCreate
from app.services.chat_service import ChatService
from app.core.security import CurrentUser, get_current_user
from app.db.mongodb import get_database

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/send")
async def send_message(
    message: MessageCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    service = ChatService(db)
    try:
        result = await service.send_message(str(current_user.id), message)
        return {"message": "Tin nhắn đã gửi", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/conversation/{friend_id}")
async def get_conversation(
    friend_id: str,
    limit: int = 50,
    skip: int = 0,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    service = ChatService(db)
    messages = await service.get_conversation(str(current_user.id), friend_id, limit, skip)
    # Đánh dấu đã đọc khi mở cuộc trò chuyện
    await service.mark_messages_as_read(str(current_user.id), friend_id)
    return messages

@router.get("/recent")
async def get_recent_chats(
    limit: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    service = ChatService(db)
    return await service.get_recent_chats(str(current_user.id), limit)

@router.get("/unread-count")
async def get_unread_count(
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    service = ChatService(db)
    count = await service.get_unread_count(str(current_user.id))
    return {"unread_count": count}

@router.put("/mark-as-read/{sender_id}")
async def mark_as_read(
    sender_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    service = ChatService(db)
    await service.mark_messages_as_read(str(current_user.id), sender_id)
    return {"message": "Đã đánh dấu đã đọc"}