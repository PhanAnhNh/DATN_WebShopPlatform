import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.routes import admin_dashboard_router, admin_posts_router, admin_shops_router, auth_routes, cart_router, category_router, follow_router, like_router, order_router, post_comments_routes, product_router, product_variants_router, report_router, review_shop_router, reviews_router, share_router, shop_router, social_posts_routes, user_routes, voucher_router  # Import router bạn đã viết

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hành động khi khởi động (Startup)
    await connect_to_mongo()
    print("--- SERVER ĐÃ SẴN SÀNG VÀ KẾT NỐI MONGODB ---")
    yield
    # Hành động khi tắt (Shutdown)
    await close_mongo_connection()
    print("--- SERVER ĐÃ ĐÓNG ---")

app = FastAPI(
    title="Đồ Án Tốt Nghiệp API",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"], # Cho phép tất cả các nguồn (hoặc ghi rõ http://localhost:5173)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các Router để sử dụng các hàm CRUD User
app.include_router(user_routes.router)
app.include_router(auth_routes.router)
app.include_router(social_posts_routes.router)
app.include_router(post_comments_routes.router)
app.include_router(like_router.router)  
app.include_router(follow_router.router)  
app.include_router(shop_router.router)  
app.include_router(product_router.router)  
app.include_router(cart_router.router)  
app.include_router(order_router.router)  
app.include_router(reviews_router.router)  
app.include_router(review_shop_router.router)  
app.include_router(report_router.router)  
app.include_router(voucher_router.router)  
app.include_router(product_variants_router.router)  
app.include_router(category_router.router)  
app.include_router(share_router.router)  
app.include_router(admin_dashboard_router.router)  
app.include_router(admin_posts_router.router)  
app.include_router(admin_shops_router.router)  # Đăng ký router admin shops

@app.get("/")
async def root():
    return {"status": "success", "message": "API đang hoạt động ổn định"}

if __name__ == "__main__":
    # Chạy server với chế độ reload (tự động khởi động lại khi bạn sửa code)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)