"""
Custom Exception Classes — Centralized error handling.

All custom exceptions inherit from a base AutoApplyError
to enable consistent error boundary patterns across the API.
"""

from fastapi import HTTPException


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


class AgentError(AutoApplyError):
    """Base for LLM agent failures surfaced to the API.

    Subclasses encode the recovery action a router should take
    (422 for malformed LLM output, 429 for rate limits, 503 for
    transient upstream issues, 500 for everything else).
    """

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message=message, status_code=status_code)


class CVProfilerError(AgentError):
    """Raised when the CV Profiler agent cannot produce valid parsed data."""

    def __init__(self, message: str = "LLM returned malformed CV data") -> None:
        super().__init__(message=message, status_code=422)


class CVOptimizerError(AgentError):
    """Raised when the CV Optimizer agent cannot produce valid output."""

    def __init__(self, message: str = "LLM returned malformed optimized CV") -> None:
        super().__init__(message=message, status_code=422)


class InterviewCoachError(AgentError):
    """Raised when the Interview Coach agent cannot produce valid output."""

    def __init__(self, message: str = "LLM returned malformed interview prep") -> None:
        super().__init__(message=message, status_code=422)


class LLMRateLimitError(AgentError):
    """Raised after exhausting retries on upstream rate limits."""

    def __init__(
        self,
        message: str = "AI provider is rate limiting requests. Try again shortly.",
    ) -> None:
        super().__init__(message=message, status_code=429)


class LLMUnavailableError(AgentError):
    """Raised after exhausting retries on transient connectivity errors."""

    def __init__(
        self,
        message: str = "AI provider is temporarily unavailable. Try again shortly.",
    ) -> None:
        super().__init__(message=message, status_code=503)


class LLMConfigurationError(AgentError):
    """Raised when the LLM key/config is invalid (operator issue)."""

    def __init__(self, message: str = "AI provider is misconfigured.") -> None:
        super().__init__(message=message, status_code=500)


def raise_http_exception(error: AutoApplyError) -> None:
    """Convert an AutoApplyError to a FastAPI HTTPException.

    Args:
        error: The application error to convert.

    Raises:
        HTTPException: With the appropriate status code and detail message.
    """
    raise HTTPException(status_code=error.status_code, detail=error.message)
