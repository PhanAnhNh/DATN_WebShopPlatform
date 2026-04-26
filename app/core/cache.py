from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import asyncio

logger = logging.getLogger(__name__)

# Simple in-memory cache storage
_cache: Dict[str, Dict[str, Any]] = {}


async def get_cached(key: str) -> Optional[Any]:
    """Get value from cache"""
    if key in _cache:
        cached = _cache[key]
        if datetime.utcnow() < cached["expires_at"]:
            logger.debug(f"Cache hit: {key}")
            return cached["data"]
        else:
            # Clean expired
            del _cache[key]
    return None


async def set_cached(key: str, value: Any, ttl: int = 60):
    """Set value to cache"""
    _cache[key] = {
        "data": value,
        "expires_at": datetime.utcnow() + timedelta(seconds=ttl)
    }
    logger.debug(f"Cached: {key} for {ttl}s")


async def invalidate_cache(pattern: str = "*"):
    """Invalidate cache by pattern"""
    global _cache
    keys_to_delete = [k for k in _cache.keys() if pattern == "*" or pattern in k]
    for key in keys_to_delete:
        del _cache[key]
    if keys_to_delete:
        logger.info(f"Invalidated {len(keys_to_delete)} cache entries matching '{pattern}'")


async def clear_cache():
    """Clear all cache"""
    global _cache
    _cache.clear()
    logger.info("Cache cleared completely")