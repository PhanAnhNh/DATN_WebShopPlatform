from datetime import datetime
import socketio
import uvicorn
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import database
from app.db.mongodb import connect_to_mongo, close_mongo_connection, get_database

# Import models
from app.models.message_model import MessageCreate

# Import routers
from app.routes import (
    address_router,
    admin_dashboard_router,
    admin_notification_router,
    admin_posts_router,
    admin_profile_router,
    admin_settings_router,
    admin_shops_router,
    auth_routes,
    cart_router,
    category_router,
    chat_routes,
    follow_router,
    friend_routes,
    like_router,
    locations_router,
    notification_router,
    order_router,
    password_routes,
    payment_router,
    post_comments_routes,
    product_router,
    product_variants_router,
    report_router,
    return_router,
    review_shop_router,
    reviews_router,
    save_router,
    share_router,
    shipping_unit_router,
    shipping_voucher_router,
    shop_auth,
    shop_customers_router,
    shop_dashboard,
    shop_orders_router,
    shop_products_router,
    shop_profile,
    shop_returns_router,
    shop_router,
    shop_settings_router,
    shop_statistics_router,
    shop_vouchers_router,
    social_posts_routes,
    user_routes,
    voucher_router
)

# Import services
from app.services.chat_service import ChatService
from app.services.cleanup_service import cleanup_expired_posts

API_PREFIX = "/api/v1"

# ====================== SOCKET.IO SETUP ======================
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[],  # ← KHÔNG duplicate
    ping_timeout=60,
    ping_interval=25
)

# ====================== LIFESPAN ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý khởi tạo và đóng server"""
    await connect_to_mongo()
    print("--- SERVER ĐÃ SẴN SÀNG VÀ KẾT NỐI MONGODB ---")

    # Background task dọn dẹp
    async def cleanup_task():
        while True:
            try:
                await asyncio.sleep(86400)  # 24 giờ
                db = get_database()
                deleted_count = await cleanup_expired_posts(db)
                if deleted_count > 0:
                    print(f"Đã xóa {deleted_count} bài viết hết hạn")
            except Exception as e:
                print(f"Lỗi cleanup task: {e}")

    task = asyncio.create_task(cleanup_task())

    yield

    # Dọn dẹp khi tắt server
    task.cancel()
    await close_mongo_connection()
    print("--- SERVER ĐÃ ĐÓNG ---")


# ====================== FASTAPI APP ======================
app = FastAPI(
    title="Đặc Sản Quê Tôi API",
    version="1.0.0",
    description="API cho ứng dụng Đặc Sản Quê Tôi",
    lifespan=lifespan
)

# CORS Middleware (chỉ cho HTTP routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ====================== SOCKET.IO EVENTS ======================
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")


# ==================== JOIN ROOM (BẮT BUỘC) ====================
@sio.event
async def join(sid, data):
    """User join room theo user_id"""
    if data and isinstance(data, dict) and data.get('user_id'):
        await sio.enter_room(sid, data['user_id'])
        print(f"✅ User {data['user_id']} joined room")


@sio.event
async def join_shop_room(sid, data):
    """Shop join room theo shop_id"""
    if data and isinstance(data, dict) and data.get('shop_id'):
        await sio.enter_room(sid, data['shop_id'])
        print(f"✅ Shop {data['shop_id']} joined room")


# ==================== SEND CHAT MESSAGE ====================
@sio.event
async def send_chat_message(sid, data):
    """Nhận tin nhắn từ client (user hoặc shop) và phát realtime"""
    try:
        db = get_database()
        chat_service = ChatService(db)

        # Gọi hàm đã sửa trong ChatService (không kiểm tra friend)
        saved_msg = await chat_service.send_message(
            sender_id=data['sender_id'],
            receiver_id=data['receiver_id'],
            content=data['content']
        )

        # Chuẩn bị dữ liệu gửi realtime
        message_data = {
            "id": str(saved_msg.get("_id")),
            "sender_id": data['sender_id'],
            "receiver_id": data['receiver_id'],
            "content": data['content'],
            "message_type": "text",
            "created_at": saved_msg["created_at"].isoformat()
        }

        # Phát tin nhắn cho cả 2 bên (room của sender và receiver)
        await sio.emit('new_message', message_data, room=data['receiver_id'])
        await sio.emit('new_message', message_data, room=data['sender_id'])

        print(f"📨 Tin nhắn từ {data['sender_id']} → {data['receiver_id']}")

    except Exception as e:
        print(f"Socket send_chat_message error: {e}")
        await sio.emit('error', {"message": str(e)}, room=data.get('sender_id'))


# ====================== INCLUDE ROUTERS ======================
app.include_router(user_routes.router, prefix=API_PREFIX)
app.include_router(auth_routes.router, prefix=API_PREFIX)
app.include_router(password_routes.router, prefix=API_PREFIX)

# Social & Chat
app.include_router(social_posts_routes.router, prefix=API_PREFIX)
app.include_router(post_comments_routes.router, prefix=API_PREFIX)
app.include_router(like_router.router, prefix=API_PREFIX)
app.include_router(follow_router.router, prefix=API_PREFIX)
app.include_router(friend_routes.router, prefix=API_PREFIX)
app.include_router(save_router.router, prefix=API_PREFIX)
app.include_router(share_router.router, prefix=API_PREFIX)
app.include_router(chat_routes.router, prefix=API_PREFIX)

# Shop & Product
app.include_router(shop_router.router, prefix=API_PREFIX)
app.include_router(shop_auth.router, prefix=API_PREFIX)
app.include_router(shop_profile.router, prefix=API_PREFIX)
app.include_router(shop_customers_router.router, prefix=API_PREFIX)
app.include_router(shop_products_router.router, prefix=API_PREFIX)
app.include_router(product_router.router, prefix=API_PREFIX)
app.include_router(category_router.router, prefix=API_PREFIX)
app.include_router(product_variants_router.router, prefix=API_PREFIX)
app.include_router(locations_router.router, prefix=API_PREFIX)

# Cart, Order, Payment
app.include_router(cart_router.router, prefix=API_PREFIX)
app.include_router(order_router.router, prefix=API_PREFIX)
app.include_router(payment_router.router, prefix=API_PREFIX)

# Others
app.include_router(address_router.router, prefix=API_PREFIX)
app.include_router(reviews_router.router, prefix=API_PREFIX)
app.include_router(review_shop_router.router, prefix=API_PREFIX)
app.include_router(voucher_router.router, prefix=API_PREFIX)
app.include_router(shipping_unit_router.router, prefix=API_PREFIX)
app.include_router(shipping_voucher_router.router, prefix=API_PREFIX)
app.include_router(return_router.router, prefix=API_PREFIX)
app.include_router(report_router.router, prefix=API_PREFIX)

# Admin
app.include_router(admin_dashboard_router.router, prefix=API_PREFIX)
app.include_router(admin_notification_router.router, prefix=API_PREFIX)
app.include_router(admin_posts_router.router, prefix=API_PREFIX)
app.include_router(admin_shops_router.router, prefix=API_PREFIX)
app.include_router(admin_profile_router.router, prefix=API_PREFIX)
app.include_router(admin_settings_router.router, prefix=API_PREFIX)

# Notification
app.include_router(notification_router.router, prefix=API_PREFIX)

# Shop Management
app.include_router(shop_dashboard.router, prefix=API_PREFIX)
app.include_router(shop_orders_router.router, prefix=API_PREFIX)
app.include_router(shop_returns_router.router, prefix=API_PREFIX)
app.include_router(shop_settings_router.router, prefix=API_PREFIX)
app.include_router(shop_statistics_router.router, prefix=API_PREFIX)
app.include_router(shop_vouchers_router.router, prefix=API_PREFIX)


# ====================== MOUNT SOCKET.IO ======================
socket_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path="/socket.io"
)
app.mount("/socket.io", socket_app)


# ====================== ROOT ENDPOINTS ======================
@app.get("/")
async def root():
    return {
        "status": "success",
        "message": "API Đặc Sản Quê Tôi đang hoạt động",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    try:
        db = get_database()
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )