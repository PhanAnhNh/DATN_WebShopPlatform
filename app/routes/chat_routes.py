# app/routes/chat_routes.py
from venv import logger

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.services.chat_service import ChatService
from app.core.security import get_current_user, get_current_shop_owner, CurrentUser
from app.db.mongodb import get_database
import socketio

router = APIRouter(prefix="/chat", tags=["Chat"])

sio_server = None

def set_socket_server(sio):
    global sio_server
    sio_server = sio

@router.post("/send")
async def send_message(
    receiver_id: str,
    content: str,
    message_type: str = "text",
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Gửi tin nhắn (user -> user hoặc user -> shop)"""
    service = ChatService(db)
    try:
        result = await service.send_message(
            sender_id=str(current_user.id),
            receiver_id=receiver_id,
            content=content,
            sender_type="user",
            message_type=message_type
        )
        
        # Phát socket realtime cho cả 2 bên
        if sio_server:
            message_data = {
                "id": str(result["_id"]),
                "sender_id": str(current_user.id),
                "receiver_id": receiver_id,
                "content": content,
                "message_type": message_type,
                "created_at": result["created_at"].isoformat() if result.get("created_at") else None,
                "is_read": False
            }
            # Quan trọng: Gửi đến room của receiver (có thể là user hoặc shop)
            await sio_server.emit('new_message', message_data, room=receiver_id)
            # Gửi đến room của sender
            await sio_server.emit('new_message', message_data, room=str(current_user.id))
            
            logger.info(f"Socket emitted to rooms: {receiver_id} and {current_user.id}")
        
        return {"message": "Tin nhắn đã gửi", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/shop/send")
async def shop_send_message(
    receiver_id: str,
    content: str,
    message_type: str = "text",
    current_shop: CurrentUser = Depends(get_current_shop_owner),
    db = Depends(get_database)
):
    """Shop gửi tin nhắn cho user"""
    service = ChatService(db)
    try:
        result = await service.send_message(
            sender_id=str(current_shop.shop_id),
            receiver_id=receiver_id,
            content=content,
            sender_type="shop",
            message_type=message_type
        )
        
        # Phát socket realtime cho cả 2 bên
        if sio_server:
            message_data = {
                "id": result.get("_id"),
                "sender_id": str(current_shop.shop_id),
                "receiver_id": receiver_id,
                "content": content,
                "message_type": message_type,
                "created_at": result.get("created_at").isoformat() if result.get("created_at") else None
            }
            # Gửi đến room của receiver (user)
            await sio_server.emit('new_message', message_data, room=receiver_id)
            # Gửi đến room của sender (shop)
            await sio_server.emit('new_message', message_data, room=str(current_shop.shop_id))
        
        return {"message": "Tin nhắn đã gửi", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/conversation/{other_id}")
async def get_conversation(
    other_id: str,
    limit: int = 50,
    skip: int = 0,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Lấy tin nhắn giữa user và người khác (user hoặc shop)"""
    service = ChatService(db)
    
    # Xác định loại người nhận
    from bson import ObjectId
    db_instance = db
    shop = await db_instance["shops"].find_one({"_id": ObjectId(other_id)})
    other_type = "shop" if shop else "user"
    
    messages = await service.get_conversation(
        user1_id=str(current_user.id),
        user2_id=other_id,
        limit=limit,
        skip=skip,
        user1_type="user",
        user2_type=other_type
    )
    
    # Đánh dấu đã đọc
    await service.mark_messages_as_read(str(current_user.id), other_id)
    
    return messages

@router.get("/shop/conversation/{user_id}")
async def get_shop_conversation(
    user_id: str,
    limit: int = 50,
    skip: int = 0,
    current_shop: CurrentUser = Depends(get_current_shop_owner),
    db = Depends(get_database)
):
    """Shop lấy tin nhắn với một user cụ thể"""
    service = ChatService(db)
    
    messages = await service.get_conversation(
        user1_id=str(current_shop.shop_id),
        user2_id=user_id,
        limit=limit,
        skip=skip,
        user1_type="shop",
        user2_type="user"
    )
    
    # Đánh dấu đã đọc
    await service.mark_messages_as_read(str(current_shop.shop_id), user_id)
    
    return messages

@router.get("/shop/conversations")
async def get_shop_conversations(
    current_shop: CurrentUser = Depends(get_current_shop_owner),
    db = Depends(get_database)
):
    """Lấy danh sách user đã chat với shop"""
    service = ChatService(db)
    conversations = await service.get_shop_conversations(str(current_shop.shop_id))
    return conversations

@router.get("/recent")
async def get_recent_chats(
    limit: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Lấy danh sách chat gần đây của user (bao gồm cả shop)"""
    service = ChatService(db)
    return await service.get_recent_chats(str(current_user.id), "user")

@router.get("/unread-count")
async def get_unread_count(
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    service = ChatService(db)
    count = await service.get_unread_count(str(current_user.id))
    return {"unread_count": count}

@router.get("/shop/unread-count")
async def get_shop_unread_count(
    current_shop: CurrentUser = Depends(get_current_shop_owner),
    db = Depends(get_database)
):
    service = ChatService(db)
    count = await service.get_unread_count(str(current_shop.shop_id))
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

@router.put("/shop/mark-as-read/{user_id}")
async def shop_mark_as_read(
    user_id: str,
    current_shop: CurrentUser = Depends(get_current_shop_owner),
    db = Depends(get_database)
):
    service = ChatService(db)
    await service.mark_messages_as_read(str(current_shop.shop_id), user_id)
    return {"message": "Đã đánh dấu đã đọc"}