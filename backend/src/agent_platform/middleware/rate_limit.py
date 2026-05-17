"""Sliding-window rate limiting middleware backed by Redis.

Limits each authenticated user (or IP for anonymous requests) to
``settings.RATE_LIMIT_REQUESTS`` requests per ``settings.RATE_LIMIT_WINDOW``
seconds.  Uses Redis sorted sets for an efficient sliding window.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from agent_platform.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user / per-IP sliding-window rate limiter."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip health endpoints
        if request.url.path.startswith("/health") or request.url.path == "/":
            return await call_next(request)

        settings = get_settings()
        max_requests = settings.RATE_LIMIT_REQUESTS
        window = settings.RATE_LIMIT_WINDOW

        # Identify the caller
        identity = self._get_identity(request)
        key = f"ratelimit:{identity}"

        try:
            from agent_platform.database import get_redis as _get_redis

            redis = await _get_redis()
            now = time.time()
            window_start = now - window

            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window + 1)
            results = await pipe.execute()

            current_count: int = results[2]

            if current_count > max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={
                        "Retry-After": str(window),
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(max(0, max_requests - current_count))
            return response

        except Exception:
            # If Redis is down, allow the request (fail-open)
            return await call_next(request)

    @staticmethod
    def _get_identity(request: Request) -> str:
        """Return user id from auth header, or client IP."""
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            # Use a hash of the token as identity (avoid storing token in Redis)
            import hashlib

            return hashlib.sha256(auth.encode()).hexdigest()[:16]
        return request.client.host if request.client else "unknown"
