# app/db/mongodb.py
import os
import asyncio
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class MongoDB:
    """
    MongoDB connection manager với connection pool và retry logic
    """
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    # Connection pool configuration
    MAX_POOL_SIZE: int = 100
    MIN_POOL_SIZE: int = 10
    MAX_IDLE_TIME_MS: int = 60000  # 60 seconds
    WAIT_QUEUE_TIMEOUT_MS: int = 5000  # 5 seconds
    CONNECT_TIMEOUT_MS: int = 10000  # 10 seconds
    SERVER_SELECTION_TIMEOUT_MS: int = 10000  # 10 seconds
    SOCKET_TIMEOUT_MS: int = 30000  # 30 seconds
    
    # Retry configuration
    MAX_RETRY_COUNT: int = 3
    RETRY_DELAY_SECONDS: float = 0.5
    
    # Health check
    _last_health_check: float = 0
    _health_check_interval: int = 60  # seconds
    
    @classmethod
    async def connect(cls) -> None:
        """
        Kết nối đến MongoDB Atlas với connection pool và retry logic
        """
        if cls.client is not None:
            logger.warning("MongoDB already connected")
            return
        
        retry_count = 0
        last_error = None
        
        while retry_count < cls.MAX_RETRY_COUNT:
            try:
                # Build connection options
                connection_options = {
                    # Connection pool settings
                    "maxPoolSize": cls.MAX_POOL_SIZE,
                    "minPoolSize": cls.MIN_POOL_SIZE,
                    "maxIdleTimeMS": cls.MAX_IDLE_TIME_MS,
                    "waitQueueTimeoutMS": cls.WAIT_QUEUE_TIMEOUT_MS,
                    
                    # Timeout settings
                    "connectTimeoutMS": cls.CONNECT_TIMEOUT_MS,
                    "serverSelectionTimeoutMS": cls.SERVER_SELECTION_TIMEOUT_MS,
                    "socketTimeoutMS": cls.SOCKET_TIMEOUT_MS,
                    
                    # Retry settings
                    "retryWrites": True,
                    "retryReads": True,
                    
                    # SSL/TLS settings (tối ưu cho performance)
                    "tls": True,
                    "tlsAllowInvalidCertificates": False,  # NÊN SET FALSE IN PRODUCTION
                    "tlsAllowInvalidHostnames": False,     # NÊN SET FALSE IN PRODUCTION
                }
                
                # For development only - disable SSL verification
                if settings.ENVIRONMENT == "development":
                    connection_options["tlsAllowInvalidCertificates"] = True
                    connection_options["tlsAllowInvalidHostnames"] = True
                    logger.warning(" SSL verification disabled for development")
                
                # Create client
                cls.client = AsyncIOMotorClient(
                    settings.MONGODB_URL,
                    **connection_options
                )
                
                # Test connection with timeout
                await asyncio.wait_for(
                    cls.client.admin.command('ping'),
                    timeout=5.0
                )
                
                cls.db = cls.client[settings.DATABASE_NAME]
                
                # Create indexes for better performance
                await cls._create_indexes()
                
                logger.info(f" MongoDB connected successfully to database: {settings.DATABASE_NAME}")
                logger.info(f"   Connection pool: min={cls.MIN_POOL_SIZE}, max={cls.MAX_POOL_SIZE}")
                return
                
            except asyncio.TimeoutError:
                last_error = TimeoutError("Connection timeout")
                logger.error(f" MongoDB connection timeout (attempt {retry_count + 1}/{cls.MAX_RETRY_COUNT})")
            except Exception as e:
                last_error = e
                logger.error(f" MongoDB connection failed (attempt {retry_count + 1}/{cls.MAX_RETRY_COUNT}): {str(e)}")
            
            retry_count += 1
            if retry_count < cls.MAX_RETRY_COUNT:
                await asyncio.sleep(cls.RETRY_DELAY_SECONDS * retry_count)
        
        raise last_error or Exception("Failed to connect to MongoDB after multiple retries")
    
    @classmethod
    async def disconnect(cls) -> None:
        """
        Đóng kết nối MongoDB
        """
        if cls.client is None:
            return
        
        try:
            cls.client.close()
            cls.client = None
            cls.db = None
            logger.info(" MongoDB connection closed")
        except Exception as e:
            logger.error(f" Error closing MongoDB connection: {e}")
    
    @classmethod
    async def health_check(cls) -> Dict[str, Any]:
        """
        Kiểm tra sức khỏe kết nối MongoDB
        """
        if cls.client is None:
            return {"status": "disconnected", "error": "No connection"}
        
        try:
            # Check connection with timeout
            start_time = asyncio.get_event_loop().time()
            await asyncio.wait_for(cls.client.admin.command('ping'), timeout=2.0)
            latency = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Get server status
            server_status = await cls.client.admin.command('serverStatus')
            
            return {
                "status": "connected",
                "latency_ms": round(latency, 2),
                "connections": {
                    "current": server_status.get('connections', {}).get('current', 0),
                    "available": server_status.get('connections', {}).get('available', 0)
                },
                "database": settings.DATABASE_NAME,
                "pool_size": {
                    "min": cls.MIN_POOL_SIZE,
                    "max": cls.MAX_POOL_SIZE
                }
            }
        except asyncio.TimeoutError:
            return {"status": "timeout", "error": "Health check timeout"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    @classmethod
    async def _create_indexes(cls) -> None:
        """
        Tạo indexes cho các collection để tối ưu query performance
        """
        try:
            # Orders collection indexes
            orders_collection = cls.db["orders"]
            
            # Compound index for user orders query
            await orders_collection.create_index(
                [("user_id", 1), ("created_at", -1)],
                name="idx_user_created"
            )
            
            # Index for status queries
            await orders_collection.create_index(
                [("status", 1), ("created_at", -1)],
                name="idx_status_created"
            )
            
            # Index for payment status
            await orders_collection.create_index(
                [("payment_status", 1)],
                name="idx_payment_status"
            )
            
            # Index for shop items
            await orders_collection.create_index(
                [("items.shop_id", 1)],
                name="idx_shop_items"
            )
            
            # Notifications collection indexes
            notifications_collection = cls.db["notifications"]
            await notifications_collection.create_index(
                [("user_id", 1), ("created_at", -1)],
                name="idx_user_notifications"
            )
            await notifications_collection.create_index(
                [("is_read", 1)],
                name="idx_is_read"
            )
            
            # Products collection indexes
            products_collection = cls.db["products"]
            await products_collection.create_index(
                [("stock", 1)],
                name="idx_stock"
            )
            await products_collection.create_index(
                [("sold_quantity", -1)],
                name="idx_sold_quantity"
            )
            
            # Product variants collection indexes
            variants_collection = cls.db["product_variants"]
            await variants_collection.create_index(
                [("product_id", 1)],
                name="idx_product_id"
            )
            await variants_collection.create_index(
                [("stock", 1)],
                name="idx_variant_stock"
            )
            
            # Carts collection indexes
            carts_collection = cls.db["carts"]
            await carts_collection.create_index(
                [("user_id", 1)],
                name="idx_cart_user",
                unique=True
            )
            
            logger.info(" MongoDB indexes created successfully")
            
        except Exception as e:
            logger.warning(f"  Failed to create indexes: {e}")
    
    @classmethod
    async def execute_with_retry(cls, operation, *args, **kwargs):
        """
        Execute database operation with automatic retry
        """
        last_error = None
        
        for attempt in range(cls.MAX_RETRY_COUNT):
            try:
                if cls.client is None:
                    await cls.connect()
                
                result = await operation(*args, **kwargs)
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Operation failed (attempt {attempt + 1}/{cls.MAX_RETRY_COUNT}): {str(e)}")
                
                if attempt < cls.MAX_RETRY_COUNT - 1:
                    await asyncio.sleep(cls.RETRY_DELAY_SECONDS * (attempt + 1))
                    # Try to reconnect
                    if cls.client is None:
                        await cls.connect()
        
        raise last_error


# Singleton instance for backward compatibility
db_instance = MongoDB()


async def connect_to_mongo():
    """
    Connect to MongoDB (backward compatible function)
    """
    await MongoDB.connect()


async def close_mongo_connection():
    """
    Close MongoDB connection (backward compatible function)
    """
    await MongoDB.disconnect()


def get_database():
    """
    Get database instance (backward compatible function)
    """
    return MongoDB.db


async def get_db_connection():
    """
    Get database connection with automatic health check
    """
    if MongoDB.db is None:
        await MongoDB.connect()
    
    # Periodic health check
    import time
    current_time = time.time()
    if current_time - MongoDB._last_health_check > MongoDB._health_check_interval:
        health = await MongoDB.health_check()
        if health["status"] != "connected":
            logger.warning("  Database health check failed, attempting reconnect...")
            await MongoDB.disconnect()
            await MongoDB.connect()
        MongoDB._last_health_check = current_time
    
    return MongoDB.db


# FastAPI dependency
async def get_db():
    """
    Dependency for FastAPI routes
    """
    db = await get_db_connection()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error in request: {e}")
        raise