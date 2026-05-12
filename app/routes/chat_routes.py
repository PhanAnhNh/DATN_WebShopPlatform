# app/routes/chat_routes.py
from datetime import datetime, timezone
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
            # Lấy thông tin người gửi
            from bson import ObjectId
            user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
            sender_name = user.get("full_name") or user.get("username", "Người dùng") if user else "Người dùng"
            sender_avatar = user.get("avatar_url") if user else None
            
            message_data = {
                "id": str(result["_id"]),
                "sender_id": str(current_user.id),
                "receiver_id": receiver_id,
                "content": content,
                "message_type": message_type,
                "created_at": result["created_at"].isoformat() if result.get("created_at") else None,
                "is_read": False,
                "sender_name": sender_name,
                "sender_avatar": sender_avatar
            }
            
            # Xác định room của người nhận (user hoặc shop)
            receiver_room = None
            # Kiểm tra receiver_id có phải shop không
            shop = await db["shops"].find_one({"_id": ObjectId(receiver_id)}) if ObjectId.is_valid(receiver_id) else None
            if shop:
                receiver_room = f'shop_{receiver_id}'
                logger.info(f"📨 Emitting to shop room: {receiver_room}")
            else:
                receiver_room = f'user_{receiver_id}'
                logger.info(f"📨 Emitting to user room: {receiver_room}")
            
            # Gửi đến room của receiver
            await sio_server.emit('new_message', message_data, room=receiver_room)
            
            # Gửi đến room của sender
            sender_room = f'user_{current_user.id}'
            await sio_server.emit('new_message', message_data, room=sender_room)
            
            logger.info(f"✅ Socket emitted: sender_room={sender_room}, receiver_room={receiver_room}")
        
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
            # Lấy thông tin shop
            from bson import ObjectId
            shop = await db["shops"].find_one({"_id": ObjectId(current_shop.shop_id)})
            sender_name = shop.get("name", "Cửa hàng") if shop else "Cửa hàng"
            sender_avatar = shop.get("logo_url") if shop else None
            
            message_data = {
                "id": str(result["_id"]),
                "sender_id": str(current_shop.shop_id),
                "receiver_id": receiver_id,
                "content": content,
                "message_type": message_type,
                "created_at": result["created_at"].isoformat() if result.get("created_at") else None,
                "is_read": False,
                "sender_name": sender_name,
                "sender_avatar": sender_avatar
            }
            
            # Room của receiver (user)
            receiver_room = f'user_{receiver_id}'
            await sio_server.emit('new_message', message_data, room=receiver_room)
            logger.info(f"📨 Shop sent to user room: {receiver_room}")
            
            # Room của sender (shop)
            sender_room = f'shop_{current_shop.shop_id}'
            await sio_server.emit('new_message', message_data, room=sender_room)
            logger.info(f"📨 Shop sent to shop room: {sender_room}")
        
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

# Thêm vào cuối file app/routes/chat_routes.py

@router.put("/{message_id}")
async def edit_message(
    message_id: str,
    content: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Sửa tin nhắn (chỉ người gửi mới được sửa)"""
    from bson import ObjectId
    
    service = ChatService(db)
    result = await service.edit_message(message_id, str(current_user.id), content)
    
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn hoặc không có quyền sửa")
    
    # Phát socket để cập nhật realtime
    if sio_server:
        message_data = {
            "id": message_id,
            "content": content,
            "edited": True,
            "edited_at": datetime.utcnow().isoformat()
        }
        # Gửi đến cả sender và receiver
        await sio_server.emit('message_edited', message_data, room=f'user_{result["sender_id"]}')
        await sio_server.emit('message_edited', message_data, room=f'user_{result["receiver_id"]}')
        if result.get("sender_type") == "shop":
            await sio_server.emit('message_edited', message_data, room=f'shop_{result["sender_id"]}')
        if result.get("receiver_type") == "shop":
            await sio_server.emit('message_edited', message_data, room=f'shop_{result["receiver_id"]}')
    
    return {"message": "Đã sửa tin nhắn"}

@router.put("/shop/{message_id}")
async def shop_edit_message(
    message_id: str,
    content: str,
    current_shop: CurrentUser = Depends(get_current_shop_owner),
    db = Depends(get_database)
):
    """Shop sửa tin nhắn"""
    from bson import ObjectId
    
    service = ChatService(db)
    result = await service.edit_message(message_id, str(current_shop.shop_id), content)
    
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn hoặc không có quyền sửa")
    
    if sio_server:
        message_data = {
            "id": message_id,
            "content": content,
            "edited": True,
            "edited_at": datetime.utcnow().isoformat()
        }
        await sio_server.emit('message_edited', message_data, room=f'user_{result["receiver_id"]}')
        await sio_server.emit('message_edited', message_data, room=f'shop_{result["sender_id"]}')
    
    return {"message": "Đã sửa tin nhắn"}

@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Xóa tin nhắn (chỉ người gửi mới được xóa)"""
    from bson import ObjectId
    
    service = ChatService(db)
    result = await service.delete_message(message_id, str(current_user.id))
    
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn hoặc không có quyền xóa")
    
    # Phát socket để cập nhật realtime
    if sio_server:
        await sio_server.emit('message_deleted', {"id": message_id}, room=f'user_{result["sender_id"]}')
        await sio_server.emit('message_deleted', {"id": message_id}, room=f'user_{result["receiver_id"]}')
        if result.get("sender_type") == "shop":
            await sio_server.emit('message_deleted', {"id": message_id}, room=f'shop_{result["sender_id"]}')
        if result.get("receiver_type") == "shop":
            await sio_server.emit('message_deleted', {"id": message_id}, room=f'shop_{result["receiver_id"]}')
    
    return {"message": "Đã xóa tin nhắn"}

@router.delete("/shop/{message_id}")
async def shop_delete_message(
    message_id: str,
    current_shop: CurrentUser = Depends(get_current_shop_owner),
    db = Depends(get_database)
):
    """Shop xóa tin nhắn"""
    from bson import ObjectId
    
    service = ChatService(db)
    result = await service.delete_message(message_id, str(current_shop.shop_id))
    
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn hoặc không có quyền xóa")
    
    if sio_server:
        await sio_server.emit('message_deleted', {"id": message_id}, room=f'user_{result["receiver_id"]}')
        await sio_server.emit('message_deleted', {"id": message_id}, room=f'shop_{result["sender_id"]}')
    
    return {"message": "Đã xóa tin nhắn"}