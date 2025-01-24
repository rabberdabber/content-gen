from functools import wraps

from fastapi import Request, Response
from redis import asyncio as aioredis
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import redis_settings

# Create Redis connection
redis = aioredis.from_url(redis_settings.REDIS_URL, encoding="utf-8", decode_responses=True)

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=redis_settings.REDIS_URL,
    strategy="fixed-window",
)

def ai_public_rate_limit():
    """Rate limit decorator for public routes"""
    def decorator(func):
        @limiter.limit(f"{redis_settings.PUBLIC_RATE_LIMIT_AI_MINUTE}/minute")
        @limiter.limit(f"{redis_settings.PUBLIC_RATE_LIMIT_AI_HOUR}/hour")
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def ai_protected_rate_limit():
    """Rate limit decorator for protected routes"""
    def decorator(func):
        @limiter.limit(f"{redis_settings.PROTECTED_RATE_LIMIT_AI_MINUTE}/minute")
        @limiter.limit(f"{redis_settings.PROTECTED_RATE_LIMIT_AI_HOUR}/hour")
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def login_rate_limit():
    """Rate limit decorator for login routes"""
    def decorator(func):
        @limiter.limit(f"{redis_settings.RATE_LIMIT_LOGIN_MINUTE}/minute")
        @limiter.limit(f"{redis_settings.RATE_LIMIT_LOGIN_HOUR}/hour")
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handler for rate limit exceeded exceptions"""
    return Response(
        content={"detail": f"Rate limit exceeded: {str(exc)}"},
        status_code=429,
        media_type="application/json"
    )
