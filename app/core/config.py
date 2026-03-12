from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # App Config
    PROJECT_NAME: str = "My E-commerce App"
    API_V1_STR: str = "/api/v1"
    
    # MongoDB Config
    MONGODB_URL: str
    DATABASE_NAME: str

    # Security Config
    SECRET_KEY: str  # Chạy lệnh 'openssl rand -hex 32' để tạo
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 tuần

    class Config:
        env_file = ".env" # Tự động đọc từ file .env của bạn

settings = Settings()