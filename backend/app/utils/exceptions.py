"""
Custom Exception Classes — Centralized error handling.

All custom exceptions inherit from a base AutoApplyError
to enable consistent error boundary patterns across the API.
"""

from fastapi import HTTPException, status


class AutoApplyError(Exception):
    """Base exception for all Auto-Apply application errors.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code for API responses.
    """

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AutoApplyError):
    """Raised when a requested resource does not exist.

    Args:
        resource: Name of the resource type (e.g., "User", "Job").
        identifier: The ID or key that was not found.
    """

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} with identifier '{identifier}' not found.",
            status_code=404,
        )


class DuplicateError(AutoApplyError):
    """Raised when attempting to create a resource that already exists.

    Args:
        resource: Name of the resource type.
        field: The field that caused the conflict (e.g., "email").
    """

    def __init__(self, resource: str, field: str) -> None:
        super().__init__(
            message=f"{resource} with this {field} already exists.",
            status_code=409,
        )


class UnauthorizedError(AutoApplyError):
    """Raised when authentication fails or credentials are invalid."""

    def __init__(self, message: str = "Invalid credentials.") -> None:
        super().__init__(message=message, status_code=401)


class ForbiddenError(AutoApplyError):
    """Raised when a user lacks permission for the requested action."""

    def __init__(self, message: str = "Access denied.") -> None:
        super().__init__(message=message, status_code=403)


class InsufficientPeersError(AutoApplyError):
    """Raised when benchmark group has fewer than 30 peers (GDPR threshold).

    Args:
        group_size: The actual number of available peers.
        required: The minimum required (default 30).
    """

    def __init__(self, group_size: int, required: int = 30) -> None:
        super().__init__(
            message=(
                f"Insufficient peers for benchmarking: {group_size} available, "
                f"{required} required. No comparative score will be generated."
            ),
            status_code=422,
        )


def raise_http_exception(error: AutoApplyError) -> None:
    """Convert an AutoApplyError to a FastAPI HTTPException.

    Args:
        error: The application error to convert.

    Raises:
        HTTPException: With the appropriate status code and detail message.
    """
    raise HTTPException(status_code=error.status_code, detail=error.message)
