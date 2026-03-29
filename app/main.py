# main.py
from datetime import datetime

import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.mongodb import connect_to_mongo, close_mongo_connection, get_database
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
    follow_router,
    friend_routes,
    like_router,
    notification_router,
    order_router,
    payment_router,
    post_comments_routes,
    product_router,
    product_variants_router,
    report_router,
    return_router,
    review_shop_router,
    reviews_router,
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
from app.services.cleanup_service import cleanup_expired_posts  # Thêm import

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời ứng dụng"""
    # Khởi tạo kết nối database
    await connect_to_mongo()
    print("--- SERVER ĐÃ SẴN SÀNG VÀ KẾT NỐI MONGODB ---")
    
    # Khởi tạo background task để xóa bài viết hết hạn
    async def cleanup_task():
        """Chạy mỗi ngày để xóa bài viết đã bị xóa tạm thời quá 10 ngày"""
        while True:
            try:
                # Chờ 24 giờ
                await asyncio.sleep(86400)
                db = get_database()
                deleted_count = await cleanup_expired_posts(db)
                if deleted_count > 0:
                    print(f"Đã xóa {deleted_count} bài viết hết hạn")
            except Exception as e:
                print(f"Lỗi khi xóa bài viết hết hạn: {e}")
    
    # Chạy background task
    task = asyncio.create_task(cleanup_task())
    
    yield
    
    # Dọn dẹp khi tắt server
    task.cancel()
    await close_mongo_connection()
    print("--- SERVER ĐÃ ĐÓNG ---")


app = FastAPI(
    title="Đồ Án Tốt Nghiệp API",
    version="1.0.0",
    description="API cho ứng dụng Đặc Sản Quê Tôi",
    lifespan=lifespan
)

# CORS Configuration
# Update your CORS configuration in main.py
# main.py - phần CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# ========================
# Đăng ký các Router
# ========================

# User & Auth
app.include_router(user_routes.router, prefix=API_PREFIX)
app.include_router(auth_routes.router, prefix=API_PREFIX)

# Social Posts & Comments
app.include_router(social_posts_routes.router, prefix=API_PREFIX)
app.include_router(post_comments_routes.router, prefix=API_PREFIX)
app.include_router(like_router.router, prefix=API_PREFIX)
app.include_router(follow_router.router, prefix=API_PREFIX)
app.include_router(share_router.router, prefix=API_PREFIX)
app.include_router(friend_routes.router, prefix=API_PREFIX)
app.include_router(follow_router.router, prefix=API_PREFIX)

# Shop
app.include_router(shop_router.router, prefix=API_PREFIX)
app.include_router(shop_auth.router, prefix=API_PREFIX)
app.include_router(shop_profile.router, prefix=API_PREFIX)
app.include_router(shop_customers_router.router, prefix=API_PREFIX)
app.include_router(shop_products_router.router, prefix=API_PREFIX)
app.include_router(shop_orders_router.router, prefix=API_PREFIX)
app.include_router(shop_dashboard.router, prefix=API_PREFIX)
app.include_router(shop_statistics_router.router, prefix=API_PREFIX)
app.include_router(shop_returns_router.router, prefix=API_PREFIX)
app.include_router(shop_settings_router.router, prefix=API_PREFIX)
app.include_router(shop_vouchers_router.router, prefix=API_PREFIX)
app.include_router(shipping_unit_router.router, prefix=API_PREFIX)
app.include_router(shop_settings_router.router, prefix=API_PREFIX)
app.include_router(admin_settings_router.router, prefix=API_PREFIX)

# Products
app.include_router(product_router.router, prefix=API_PREFIX)
app.include_router(product_variants_router.router, prefix=API_PREFIX)
app.include_router(category_router.router, prefix=API_PREFIX)
app.include_router(return_router.router, prefix=API_PREFIX)

# Cart & Orders
app.include_router(cart_router.router, prefix=API_PREFIX)
app.include_router(order_router.router, prefix=API_PREFIX)
app.include_router(payment_router.router, prefix=API_PREFIX)

# Reviews
app.include_router(reviews_router.router, prefix=API_PREFIX)
app.include_router(review_shop_router.router, prefix=API_PREFIX)

# Vouchers
app.include_router(voucher_router.router, prefix=API_PREFIX)
app.include_router(shipping_voucher_router.router, prefix=API_PREFIX)

# Address
app.include_router(address_router.router, prefix=API_PREFIX)

# Reports
app.include_router(report_router.router, prefix=API_PREFIX)

# Notifications
app.include_router(notification_router.router, prefix=API_PREFIX)
app.include_router(admin_notification_router.router, prefix=API_PREFIX)

# Admin
app.include_router(admin_dashboard_router.router, prefix=API_PREFIX)
app.include_router(admin_posts_router.router, prefix=API_PREFIX)
app.include_router(admin_shops_router.router, prefix=API_PREFIX)
app.include_router(admin_profile_router.router, prefix=API_PREFIX)


@app.get("/")
async def root():
    """Endpoint kiểm tra server hoạt động"""
    return {
        "status": "success",
        "message": "API đang hoạt động ổn định",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Kiểm tra sức khỏe server"""
    try:
        db = get_database()
        await db.command("ping")
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )