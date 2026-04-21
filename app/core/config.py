# app/core/config.py
from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    # App Config
    PROJECT_NAME: str = "Đặc Sản Quê Tôi"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # MongoDB Config
    MONGODB_URL: str
    DATABASE_NAME: str
    
    # Security Config
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 ngày (60*24*7)
    
    # CORS Config
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ]
    
    # Email Config
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""
    FROM_NAME: str = "Đặc Sản Quê Tôi"
    
    # OTP Config
    OTP_EXPIRE_MINUTES: int = 5
    OTP_LENGTH: int = 6
    
    # Upload Config
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    
    MAPBOX_ACCESS_TOKEN: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"

# Tạo instance settings
settings = Settings()