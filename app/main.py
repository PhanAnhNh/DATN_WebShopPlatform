# main.py
from datetime import datetime
import socketio
import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

# Import database
from app.db.mongodb import connect_to_mongo, close_mongo_connection, get_database, MongoDB

# Import config
from app.core.config import settings

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
    favorite_router,
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
    review_router,
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
    traceability_router,
    upload_router,
    user_routes,
    voucher_router
)

# Import services
from app.services.chat_service import ChatService
from app.services.cleanup_service import cleanup_expired_posts
from app.services.sepay_poller import SePayPoller

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(settings.LOG_FILE) if settings.LOG_FILE else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)
sepay_poller = None 

API_PREFIX = settings.API_V1_STR

# ====================== SOCKET.IO SETUP ======================
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.cors_origins if settings.is_production else [],
    ping_timeout=60,
    ping_interval=25,
    logger=logger,
    engineio_logger=logger
)

# ====================== LIFESPAN ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý khởi tạo và đóng server"""
    global sepay_poller
    
    logger.info(" Starting server...")
    
    # Connect to MongoDB
    try:
        await connect_to_mongo()
        logger.info(" MongoDB connected successfully")
        health = await MongoDB.health_check()
        logger.info(f" MongoDB health: {health}")
    except Exception as e:
        logger.error(f" Failed to connect to MongoDB: {e}")
        raise

    # Background task dọn dẹp post (24h)
    async def cleanup_task():
        while True:
            try:
                await asyncio.sleep(86400)
                db = get_database()
                deleted_count = await cleanup_expired_posts(db)
                if deleted_count > 0:
                    logger.info(f" Deleted {deleted_count} expired posts")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f" Cleanup task error: {e}")

    # Background task dọn dẹp order pending_payment (1 phút)
    async def cleanup_expired_orders_task():
        while True:
            try:
                await asyncio.sleep(60)
                db = get_database()
                from app.services.order_service import OrderService
                order_service = OrderService(db)
                deleted_count = await order_service.delete_expired_pending_payment_orders()
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired pending_payment orders")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup expired orders task error: {e}")

    # Start background tasks
    cleanup = asyncio.create_task(cleanup_task())
    cleanup_orders = asyncio.create_task(cleanup_expired_orders_task())
    logger.info(" Cleanup tasks started")

    # ========== SERVER RUNNING ==========
    yield

    # ========== SHUTDOWN ==========
    logger.info(" Shutting down server...")
    
    if sepay_poller:
        await sepay_poller.stop()
    
    cleanup.cancel()
    cleanup_orders.cancel()
    
    try:
        await cleanup
        await cleanup_orders
    except asyncio.CancelledError:
        pass
    
    await close_mongo_connection()
    logger.info(" Server shutdown complete")

# ====================== FASTAPI APP ======================
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=f"API cho ứng dụng {settings.PROJECT_NAME}",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# ====================== EXCEPTION HANDLERS ======================
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.status_code,
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": 500,
            "message": "Internal server error" if settings.is_production else str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# ====================== SOCKET.IO EVENTS ======================
@sio.event
async def connect(sid, environ):
    client_host = environ.get('REMOTE_ADDR', 'unknown')
    logger.info(f" Client connected: {sid} from {client_host}")
    return True

@sio.event
async def disconnect(sid):
    logger.info(f" Client disconnected: {sid}")

@sio.on('ping')
async def handle_ping(sid, data):
    """Handle ping from client"""
    await sio.emit('pong', {'timestamp': datetime.utcnow().isoformat()}, room=sid)

@sio.event
async def join(sid, data):
    """User hoặc Shop join room"""
    try:
        if data and isinstance(data, dict):
            # User join
            if data.get('user_id'):
                user_id = str(data['user_id'])
                await sio.enter_room(sid, user_id)
                logger.info(f"✅ User {user_id} joined room {user_id}")
                # Log số lượng rooms hiện tại
                rooms = sio.rooms(sid)
                logger.info(f"   Rooms for {sid}: {rooms}")
                await sio.emit('joined', {'user_id': user_id, 'status': 'success'}, room=sid)
            
            # Shop join
            if data.get('shop_id'):
                shop_id = str(data['shop_id'])
                await sio.enter_room(sid, shop_id)
                logger.info(f"✅ Shop {shop_id} joined room {shop_id}")
                rooms = sio.rooms(sid)
                logger.info(f"   Rooms for {sid}: {rooms}")
                await sio.emit('joined', {'shop_id': shop_id, 'status': 'success'}, room=sid)
    except Exception as e:
        logger.error(f"Join error: {e}")

@sio.event
async def leave(sid, data):
    """User leave room"""
    try:
        if data and isinstance(data, dict):
            room = data.get('user_id') or data.get('shop_id')
            if room:
                await sio.leave_room(sid, str(room))
                logger.info(f" Client {sid} left room {room}")
                await sio.emit('left', {'room': room, 'status': 'success'}, room=sid)
    except Exception as e:
        logger.error(f" Leave error: {e}")

@sio.event
async def send_chat_message(sid, data):
    """Gửi tin nhắn realtime (KHÔNG lưu database, chỉ phát)"""
    try:
        required_fields = ['sender_id', 'receiver_id', 'content']
        for field in required_fields:
            if field not in data:
                await sio.emit('error', {'message': f'Missing field: {field}'}, room=sid)
                return

        # Chuẩn bị dữ liệu để gửi realtime (KHÔNG lưu database)
        message_data = {
            "id": 'socket-' + str(datetime.utcnow().timestamp()),
            "sender_id": data['sender_id'],
            "receiver_id": data['receiver_id'],
            "content": data['content'],
            "message_type": "text",
            "created_at": datetime.utcnow().isoformat()
        }

        # Gửi đến receiver và sender
        await sio.emit('new_message', message_data, room=data['receiver_id'])
        await sio.emit('new_message', message_data, room=data['sender_id'])
        await sio.emit('message_sent', {'id': message_data['id'], 'status': 'delivered'}, room=sid)

        logger.info(f"Socket realtime message from {data['sender_id']} to {data['receiver_id']}")

    except Exception as e:
        logger.error(f"Socket send_chat_message error: {e}")
        await sio.emit('error', {"message": str(e)}, room=sid)

@sio.event
async def typing_start(sid, data):
    """Notify when user starts typing"""
    try:
        if data and isinstance(data, dict):
            receiver_id = data.get('receiver_id')
            sender_id = data.get('sender_id')
            if receiver_id and sender_id:
                await sio.emit('user_typing', {
                    'sender_id': sender_id,
                    'is_typing': True
                }, room=receiver_id)
    except Exception as e:
        logger.error(f" Typing start error: {e}")

@sio.event
async def typing_stop(sid, data):
    """Notify when user stops typing"""
    try:
        if data and isinstance(data, dict):
            receiver_id = data.get('receiver_id')
            sender_id = data.get('sender_id')
            if receiver_id and sender_id:
                await sio.emit('user_typing', {
                    'sender_id': sender_id,
                    'is_typing': False
                }, room=receiver_id)
    except Exception as e:
        logger.error(f" Typing stop error: {e}")
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
app.include_router(favorite_router.router, prefix=API_PREFIX)
app.include_router(review_router.router, prefix=API_PREFIX)

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
app.include_router(traceability_router.router, prefix=API_PREFIX)
app.include_router(upload_router.router, prefix=API_PREFIX)

# Log all registered routes in debug mode
if settings.DEBUG:
    logger.info(" Registered routes:")
    for route in app.routes:
        logger.info(f"  {route.methods if hasattr(route, 'methods') else 'N/A'} {route.path}")

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
        "message": f"API {settings.PROJECT_NAME} đang hoạt động",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint cho monitoring
    """
    try:
        # Check database
        db = get_database()
        await db.command("ping")
        
        # Get MongoDB health details
        db_health = await MongoDB.health_check()
        
        return {
            "status": "healthy",
            "database": "connected",
            "mongodb": db_health,
            "environment": settings.ENVIRONMENT,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get("/info")
async def server_info():
    """Server information endpoint"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "api_prefix": API_PREFIX,
        "features": {
            "email": settings.EMAIL_ENABLED,
            "cache": settings.ENABLE_CACHE,
            "async_email": settings.ENABLE_ASYNC_EMAIL,
            "redis": settings.redis_enabled
        }
    }


# ====================== RUN SERVER ======================
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        workers=settings.WORKERS if not settings.DEBUG else 1,
        reload_dirs=["app"] if settings.DEBUG else None
    )