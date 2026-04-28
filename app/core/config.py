# app/core/config.py
from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any
from pydantic import Field, field_validator, ValidationInfo
import os
from pathlib import Path

# Get root directory
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings with validation"""
    
    # ==================== APP CONFIG ====================
    PROJECT_NAME: str = "Đặc Sản Quê Tôi"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    
    # Server Config
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    
    # ==================== MongoDB Config ====================
    MONGODB_URL: str
    DATABASE_NAME: str
    
    # MongoDB Connection Pool
    MONGODB_MAX_POOL_SIZE: int = 100
    MONGODB_MIN_POOL_SIZE: int = 10
    MONGODB_MAX_IDLE_TIME_MS: int = 60000
    MONGODB_CONNECT_TIMEOUT_MS: int = 10000
    MONGODB_SOCKET_TIMEOUT_MS: int = 30000
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 10000
    
    # ==================== Security Config ====================
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Password Config
    PASSWORD_MIN_LENGTH: int = 6
    PASSWORD_MAX_LENGTH: int = 50
    
    # ==================== CORS Config ====================
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]
    
    # Production CORS (will be appended if in production)
    PRODUCTION_CORS_ORIGINS: List[str] = [
        "https://dacsanqueto i.com",
        "https://www.dacsanqueto i.com",
        "https://api.dacsanqueto i.com",
    ]
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: Any, info: ValidationInfo) -> List[str]:
        """Validate and merge CORS origins based on environment"""
        if isinstance(v, str):
            v = [origin.strip() for origin in v.split(",")]
        
        # Add production origins if in production mode
        if hasattr(cls, "ENVIRONMENT") and cls.ENVIRONMENT == "production":
            if hasattr(cls, "PRODUCTION_CORS_ORIGINS"):
                v.extend(cls.PRODUCTION_CORS_ORIGINS)
        
        return list(set(v))  # Remove duplicates
    
    # ==================== Email Config ====================
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""
    FROM_NAME: str = "Đặc Sản Quê Tôi"
    
    # Email Templates
    EMAIL_TEMPLATE_DIR: str = str(ROOT_DIR / "app" / "templates" / "emails")
    EMAIL_ENABLED: bool = True
    EMAIL_SEND_TIMEOUT: int = 10  # seconds
    
    @field_validator("SMTP_PORT")
    @classmethod
    def validate_smtp_port(cls, v: int) -> int:
        """Validate SMTP port"""
        if v not in [25, 465, 587, 2525]:
            raise ValueError(f"Invalid SMTP port: {v}. Must be 25, 465, 587, or 2525")
        return v
    
    # ==================== OTP Config ====================
    OTP_EXPIRE_MINUTES: int = 5
    OTP_LENGTH: int = 6
    OTP_MAX_ATTEMPTS: int = 3
    OTP_RATE_LIMIT_SECONDS: int = 60  # Rate limit: 1 OTP per 60 seconds
    
    # ==================== Upload Config ====================
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    MAX_UPLOAD_FILES: int = 10
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/jpg", "image/webp", "image/gif"]
    UPLOAD_DIR: str = str(ROOT_DIR / "uploads")
    UPLOAD_URL_PREFIX: str = "/uploads"
    
    # Cloud Storage (Optional)
    CLOUD_STORAGE_PROVIDER: Optional[str] = None  # "aws", "gcp", "azure"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_S3_REGION: str = "ap-southeast-1"
    
    # ==================== Redis Config (for caching) ====================
    REDIS_URL: Optional[str] = None
    REDIS_CACHE_TTL: int = 3600  # 1 hour
    REDIS_SESSION_TTL: int = 86400  # 24 hours
    
    @property
    def redis_enabled(self) -> bool:
        """Check if Redis is configured"""
        return bool(self.REDIS_URL)
    
    # ==================== Rate Limiting ====================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100  # requests per minute
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # ==================== Payment Config ====================
    # VNPay
    VNPAY_TMN_CODE: Optional[str] = None
    VNPAY_HASH_SECRET: Optional[str] = None
    VNPAY_URL: str = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    VNPAY_RETURN_URL: str = "/api/v1/payments/vnpay/callback"
    
    # Momo
    MOMO_PARTNER_CODE: Optional[str] = None
    MOMO_ACCESS_KEY: Optional[str] = None
    MOMO_SECRET_KEY: Optional[str] = None
    MOMO_URL: str = "https://test-payment.momo.vn/v2/gateway/api/create"
    MOMO_RETURN_URL: str = "/api/v1/payments/momo/callback"
    
    # PayPal
    PAYPAL_CLIENT_ID: Optional[str] = None
    PAYPAL_CLIENT_SECRET: Optional[str] = None
    PAYPAL_MODE: str = "sandbox"  # sandbox or live
    PAYPAL_RETURN_URL: str = "/api/v1/payments/paypal/callback"
    
    # ==================== Shipping Config ====================
    # GiaoHangNhanh (GHN)
    GHN_API_URL: str = "https://dev-online-gateway.ghn.vn/shiip/public-api"
    GHN_TOKEN: Optional[str] = None
    GHN_SHOP_ID: Optional[int] = None
    
    # GiaoHangTietKiem (GHTK)
    GHTK_API_URL: str = "https://services.giaohangtietkiem.vn"
    GHTK_TOKEN: Optional[str] = None
    
    # ==================== Logging Config ====================
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = str(ROOT_DIR / "logs" / "app.log")
    LOG_MAX_SIZE_MB: int = 10
    LOG_BACKUP_COUNT: int = 5
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # ==================== Admin Config ====================
    ADMIN_EMAIL: str = "admin@dacsanqueto i.com"
    ADMIN_USERNAME: str = "admin"
    
    # ==================== Third Party APIs ====================
    MAPBOX_ACCESS_TOKEN: str = ""
    GOOGLE_MAPS_API_KEY: str = ""
    FIREBASE_CREDENTIALS: Optional[str] = None
    
    # ==================== Feature Flags ====================
    ENABLE_EMAIL_VERIFICATION: bool = True
    ENABLE_SMS_NOTIFICATION: bool = False
    ENABLE_PUSH_NOTIFICATION: bool = True
    ENABLE_CACHE: bool = True
    ENABLE_ASYNC_EMAIL: bool = True

    SEPAY_API_KEY: Optional[str] = None
    SEPAY_API_URL: str = "https://my.sepay.vn/api/v1"
    SEPAY_API_KEY: Optional[str] = None
    SEPAY_WEBHOOK_SECRET: Optional[str] None  # Nếu SePay có signature
    
    BANK_BIN: str = "970415"  # VietinBank
    BANK_NUMBER: str = ""  # Số tài khoản nhận tiền
    BANK_NAME: str = ""  # Tên chủ tài khoản

    BACKEND_URL: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from .env
        
    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value"""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v
    
    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str, info: ValidationInfo) -> str:
        """Validate secret key length"""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v
    
    @field_validator("MONGODB_URL", mode="before")
    @classmethod
    def validate_mongodb_url(cls, v: str) -> str:
        """Validate MongoDB connection string"""
        if not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MONGODB_URL must start with mongodb:// or mongodb+srv://")
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode"""
        return self.ENVIRONMENT == "staging"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.ENVIRONMENT == "production"
    
    @property
    def mongodb_settings(self) -> Dict[str, Any]:
        """Get MongoDB connection settings"""
        return {
            "maxPoolSize": self.MONGODB_MAX_POOL_SIZE,
            "minPoolSize": self.MONGODB_MIN_POOL_SIZE,
            "maxIdleTimeMS": self.MONGODB_MAX_IDLE_TIME_MS,
            "connectTimeoutMS": self.MONGODB_CONNECT_TIMEOUT_MS,
            "socketTimeoutMS": self.MONGODB_SOCKET_TIMEOUT_MS,
            "serverSelectionTimeoutMS": self.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            "retryWrites": True,
            "retryReads": True,
            "tls": self.is_production,  # Enable TLS only in production
        }
    
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins with environment-specific rules"""
        origins = self.BACKEND_CORS_ORIGINS.copy()
        
        # In production, allow all configured origins
        if self.is_production:
            origins.extend(self.PRODUCTION_CORS_ORIGINS)
        
        # Remove duplicates
        return list(set(origins))
    
    @property
    def smtp_config(self) -> Dict[str, Any]:
        """Get SMTP configuration"""
        return {
            "server": self.SMTP_SERVER,
            "port": self.SMTP_PORT,
            "username": self.SMTP_USERNAME,
            "password": self.SMTP_PASSWORD,
            "from_email": self.FROM_EMAIL,
            "from_name": self.FROM_NAME,
            "timeout": self.EMAIL_SEND_TIMEOUT,
        }
    
    @property
    def is_smtp_configured(self) -> bool:
        """Check if SMTP is properly configured"""
        return bool(self.SMTP_USERNAME and self.SMTP_PASSWORD and self.FROM_EMAIL)


# Create helper function to load settings
def get_settings() -> Settings:
    """Get settings instance (singleton pattern)"""
    return Settings()


# Singleton instance
settings = get_settings()


# Create directories if they don't exist
def create_directories():
    """Create necessary directories"""
    directories = [
        settings.UPLOAD_DIR,
        str(ROOT_DIR / "logs"),
        settings.EMAIL_TEMPLATE_DIR,
    ]
    
    for directory in directories:
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)


# Create directories on import
if not settings.is_production:
    create_directories()