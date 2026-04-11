from fastapi import APIRouter, Depends, HTTPException
from app.models.message_model import MessageCreate
from app.services.chat_service import ChatService
from app.core.security import get_current_shop_owner, get_current_user
from app.db.mongodb import get_database

router = APIRouter(prefix="/chat", tags=["Chat Shop"])

# ====================== USER → SHOP ======================
@router.post("/user-to-shop")
async def send_message_user_to_shop(
    message: MessageCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    service = ChatService(db)
    result = await service.send_message_user_to_shop(
        str(current_user.id), message.receiver_id, message
    )
    return {"message": "Đã gửi tin nhắn cho shop", "data": result}


@router.get("/conversation/shop/{shop_id}")
async def get_user_shop_conversation(
    shop_id: str,
    limit: int = 50,
    skip: int = 0,
    current_user=Depends(get_current_user),
    db=Depends(get_database)
):
    service = ChatService(db)
    messages = await service.get_conversation_user_shop(
        str(current_user.id), shop_id, limit, skip
    )
    await service.mark_messages_as_read(str(current_user.id), shop_id)
    return messages


# ====================== SHOP SIDE ======================
@router.post("/shop-to-user")
async def send_message_shop_to_user(
    message: MessageCreate,
    current_shop=Depends(get_current_shop_owner),
    db=Depends(get_database)
):
    service = ChatService(db)
    result = await service.send_message_shop_to_user(
        str(current_shop.id), message.receiver_id, message   # ← SỬA Ở ĐÂY
    )
    return {"message": "Đã trả lời khách hàng", "data": result}


@router.get("/shop/conversation/{user_id}")
async def get_shop_user_conversation(
    user_id: str,
    limit: int = 50,
    skip: int = 0,
    current_shop=Depends(get_current_shop_owner),
    db=Depends(get_database)
):
    service = ChatService(db)
    messages = await service.get_conversation_user_shop(
        user_id, str(current_shop.id), limit, skip          # ← SỬA Ở ĐÂY
    )
    await service.mark_messages_as_read(str(current_shop.id), user_id)
    return messages


@router.get("/shop/recent")
async def get_shop_recent_chats(
    limit: int = 20,
    current_shop=Depends(get_current_shop_owner),
    db=Depends(get_database)
):
    service = ChatService(db)
    shop_id = str(current_shop.id)   # lấy từ token
    return await service.get_shop_recent_chats(shop_id, limit)