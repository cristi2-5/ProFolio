"""
Rate Limiting Middleware.

Protects API endpoints from abuse using slowapi (Flask-Limiter for FastAPI).
Applies per-IP rate limits to prevent brute-force attacks and resource exhaustion.
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, FastAPI

# Initialize limiter with IP-based key function
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


def setup_rate_limiting(app: FastAPI) -> None:
    """Configure rate limiting middleware for the FastAPI application.

    Applies the following rate limits:
    - Default: 100 requests per minute per IP address
    - Can be overridden per-route using @limiter.limit() decorator

    Args:
        app: FastAPI application instance to configure.

    Usage:
        from app.middleware.rate_limit import setup_rate_limiting, limiter

        app = FastAPI()
        setup_rate_limiting(app)

        @app.get("/login")
        @limiter.limit("5/minute")  # Stricter limit for login
        async def login(request: Request):
            ...

    Notes:
        - Rate limits are tracked per IP address (X-Forwarded-For aware)
        - Exceeding limits returns 429 Too Many Requests
        - Limits reset on a sliding window (not fixed intervals)
    """
    app.state.limiter = limiter
    app.state.default_limits = DEFAULT_RATE_LIMITS
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
