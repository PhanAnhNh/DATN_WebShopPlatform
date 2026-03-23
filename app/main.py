# main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.routes import (
    address_router, admin_dashboard_router, shop_vouchers_router, 
    admin_posts_router, admin_shops_router, auth_routes, cart_router, 
    category_router, follow_router, like_router, order_router, 
    post_comments_routes, product_router, product_variants_router, 
    report_router, review_shop_router, reviews_router, share_router, 
    shop_auth, shop_customers_router, shop_dashboard, shop_orders_router, 
    shop_products_router, shop_profile, shop_returns_router, shop_router, 
    shop_settings_router, shop_statistics_router, social_posts_routes, 
    user_routes, voucher_router, payment_router
)

API_PREFIX = "/api/v1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    print("--- SERVER ĐÃ SẴN SÀNG VÀ KẾT NỐI MONGODB ---")
    yield
    await close_mongo_connection()
    print("--- SERVER ĐÃ ĐÓNG ---")

app = FastAPI(
    title="Đồ Án Tốt Nghiệp API",
    lifespan=lifespan
)

# CORS Configuration - SỬA LẠI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Đăng ký các Router
app.include_router(user_routes.router, prefix=API_PREFIX)
app.include_router(auth_routes.router, prefix=API_PREFIX)
app.include_router(social_posts_routes.router, prefix=API_PREFIX)
app.include_router(post_comments_routes.router, prefix=API_PREFIX)
app.include_router(like_router.router, prefix=API_PREFIX)
app.include_router(follow_router.router, prefix=API_PREFIX)
app.include_router(shop_router.router, prefix=API_PREFIX)  
app.include_router(product_router.router, prefix=API_PREFIX)  
app.include_router(cart_router.router, prefix=API_PREFIX)  
app.include_router(order_router.router, prefix=API_PREFIX)  
app.include_router(reviews_router.router, prefix=API_PREFIX)  
app.include_router(review_shop_router.router, prefix=API_PREFIX)  
app.include_router(report_router.router, prefix=API_PREFIX)  
app.include_router(voucher_router.router, prefix=API_PREFIX)  
app.include_router(product_variants_router.router, prefix=API_PREFIX)  
app.include_router(category_router.router, prefix=API_PREFIX)  
app.include_router(share_router.router, prefix=API_PREFIX)  
app.include_router(admin_dashboard_router.router, prefix=API_PREFIX)  
app.include_router(admin_posts_router.router, prefix=API_PREFIX)  
app.include_router(admin_shops_router.router, prefix=API_PREFIX)
app.include_router(shop_customers_router.router, prefix=API_PREFIX)
app.include_router(shop_products_router.router, prefix=API_PREFIX)
app.include_router(shop_dashboard.router, prefix=API_PREFIX)
app.include_router(shop_profile.router, prefix=API_PREFIX)
app.include_router(shop_auth.router, prefix=API_PREFIX)
app.include_router(address_router.router, prefix=API_PREFIX)
app.include_router(shop_orders_router.router, prefix=API_PREFIX)
app.include_router(shop_statistics_router.router, prefix=API_PREFIX)
app.include_router(shop_returns_router.router, prefix=API_PREFIX)  
app.include_router(shop_settings_router.router, prefix=API_PREFIX)
app.include_router(payment_router.router, prefix=API_PREFIX)
app.include_router(shop_vouchers_router.router, prefix=API_PREFIX)

@app.get("/")
async def root():
    return {"status": "success", "message": "API đang hoạt động ổn định"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)