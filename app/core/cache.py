from typing import Dict, Any, Optional, Callable
from functools import wraps
import hashlib
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Simple in-memory cache
_cache: Dict[str, Dict[str, Any]] = {}


def cache_response(ttl: int = 60, key_prefix: str = ""):
    """
    Cache decorator for FastAPI endpoints
    CHỈ DÙNG CHO GET ENDPOINTS, KHÔNG DÙNG CHO POST/PUT/DELETE
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            cache_key = _generate_cache_key(func.__name__, kwargs, key_prefix)
            
            # Check cache
            if cache_key in _cache:
                cached = _cache[cache_key]
                if datetime.utcnow() < cached["expires_at"]:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached["data"]
            
            # Execute the function - FIXED
            result = await func(*args, **kwargs)
            
            # Store in cache
            _cache[cache_key] = {
                "data": result,
                "expires_at": datetime.utcnow() + timedelta(seconds=ttl)
            }
            
            logger.debug(f"Cached {func.__name__} for {ttl}s")
            return result
        return wrapper
    return decorator


async def invalidate_cache(pattern: str = "*"):
    """Invalidate cache by pattern"""
    global _cache
    keys_to_delete = []
    
    for key in _cache.keys():
        if pattern == "*" or pattern in key:
            keys_to_delete.append(key)
    
    for key in keys_to_delete:
        del _cache[key]
    
    if keys_to_delete:
        logger.info(f"Invalidated {len(keys_to_delete)} cache entries matching '{pattern}'")


async def clear_cache():
    """Clear all cache"""
    global _cache
    _cache.clear()
    logger.info("Cache cleared completely")


def _generate_cache_key(func_name: str, kwargs: dict, prefix: str = "") -> str:
    """Generate cache key from function arguments"""
    filtered_kwargs = {}
    
    for k, v in kwargs.items():
        # Skip non-hashable objects
        if k in ["db", "request", "background_tasks", "self", "cls"]:
            continue
        
        if hasattr(v, "__call__"):
            continue
        
        try:
            json.dumps(v)
            filtered_kwargs[k] = v
        except (TypeError, ValueError):
            filtered_kwargs[k] = str(v)
    
    key_str = f"{prefix}:{func_name}:{json.dumps(filtered_kwargs, sort_keys=True, default=str)}"
    return hashlib.md5(key_str.encode()).hexdigest()