"""
Rate Limiting Utilities — slowapi limiter and key functions.

Centralises the application's slowapi ``Limiter`` instance and helper
key functions so routers and middleware share a single source of truth.
"""

from fastapi import Request
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings


def user_id_key(request: Request) -> str:
    """Return the authenticated user's id, falling back to remote address.

    Used as a slowapi ``key_func`` to rate-limit per user instead of per IP
    on endpoints that require authentication. Prefers ``request.state.user``
    when populated, otherwise decodes the bearer token from the Authorization
    header to extract the ``sub`` claim. Falls back to the remote address
    when no user can be identified.
    """
    user = getattr(request.state, "user", None)
    if user is not None:
        return str(getattr(user, "id", user))

    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        settings = get_settings()
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm],
            )
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except JWTError:
            pass

    return get_remote_address(request)


limiter = Limiter(key_func=get_remote_address)
