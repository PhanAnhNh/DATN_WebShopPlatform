import os
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

db_instance = MongoDB()

async def connect_to_mongo():
    try:
        # TẮT SSL VERIFICATION - CHỈ DÙNG CHO DEVELOPMENT
        db_instance.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            tls=True,
            tlsAllowInvalidCertificates=True,  # Cho phép certificate không hợp lệ
            tlsAllowInvalidHostnames=True,     # Cho phép hostname không khớp
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            retryWrites=True,
            retryReads=True
        )
        
        # Kiểm tra kết nối
        await db_instance.client.admin.command('ping')
        db_instance.db = db_instance.client[settings.DATABASE_NAME]
        print("--- Đã kết nối thành công tới MongoDB Atlas (với SSL disabled) ---")
    except Exception as e:
        print(f"--- Lỗi kết nối MongoDB: {e} ---")
        raise e

async def close_mongo_connection():
    if db_instance.client:
        db_instance.client.close()
        print("--- Đã đóng kết nối MongoDB ---")

def get_database():
    return db_instance.db