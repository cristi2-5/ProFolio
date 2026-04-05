"""
Security Headers Middleware.

Adds OWASP-recommended HTTP security headers to all API responses.
Protects against XSS, clickjacking, MIME sniffing, and other common attacks.
"""

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that injects security headers into all HTTP responses.

    Implements OWASP recommended headers:
    - X-Content-Type-Options: Prevents MIME-type sniffing
    - X-Frame-Options: Prevents clickjacking attacks
    - X-XSS-Protection: Enables browser XSS filtering (legacy support)
    - Strict-Transport-Security: Enforces HTTPS connections
    - Content-Security-Policy: Restricts resource loading (API context)
    - Referrer-Policy: Controls referrer information leakage

    Notes:
        - HSTS header only sent in production (requires HTTPS)
        - CSP is API-focused (no script execution expected)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and inject security headers into response.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/route handler in chain.

        Returns:
            Response: HTTP response with security headers added.
        """
        response = await call_next(request)

        # Prevent MIME-type sniffing (forces browser to respect Content-Type)
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking (disallow embedding in frames)
        response.headers["X-Frame-Options"] = "DENY"

        # Enable browser XSS filtering (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS for 1 year (only in production)
        # Note: Only enable if serving over HTTPS
        # response.headers["Strict-Transport-Security"] = (
        #     "max-age=31536000; includeSubDomains; preload"
        # )

        # Content Security Policy for API (no inline scripts expected)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )

        # Control referrer information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Remove server version disclosure
        response.headers["Server"] = "AutoApply API"

        return response


def setup_security_headers(app: FastAPI) -> None:
    """Configure security headers middleware for the FastAPI application.

    Args:
        app: FastAPI application instance to configure.

    Usage:
        from app.middleware.security_headers import setup_security_headers

        app = FastAPI()
        setup_security_headers(app)

    Notes:
        - Middleware runs for ALL routes (including error responses)
        - HSTS header commented out (enable only with HTTPS in production)
        - CSP is API-focused (adjust if serving HTML/JavaScript)
    """
    app.add_middleware(SecurityHeadersMiddleware)
