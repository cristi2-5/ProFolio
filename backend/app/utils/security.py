"""
Security Utilities — Password hashing, validation, and JWT token management.

Uses bcrypt for password hashing (OWASP recommended) and
python-jose for JWT creation/verification. Includes password
strength validation with complexity requirements.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# Bcrypt context for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Args:
        password: The plain-text password to hash.

    Returns:
        str: The bcrypt hash string.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash.

    Args:
        plain_password: The plain-text password to check.
        hashed_password: The stored bcrypt hash.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload data to encode in the token (must include "sub").
        expires_delta: Custom expiration duration. Defaults to
            settings.access_token_expire_minutes.

    Returns:
        str: The encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    """Decode and verify a JWT access token.

    Args:
        token: The JWT string to decode.

    Returns:
        dict | None: The decoded payload if valid, None if invalid/expired.
    """
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


# =====================================================================
# Password Validation
# =====================================================================


def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """Validate password strength and complexity requirements.

    Implements OWASP password strength recommendations:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    - No common weak patterns

    Args:
        password: The plain-text password to validate.

    Returns:
        Tuple[bool, List[str]]: (is_valid, list_of_errors)
            - is_valid: True if password meets all requirements
            - list_of_errors: List of requirement violations (empty if valid)

    Usage:
        is_valid, errors = validate_password_strength("MyPassword123!")
        if not is_valid:
            raise ValueError(f"Password requirements not met: {', '.join(errors)}")
    """
    errors = []

    # Length requirement (minimum 8 characters)
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    # Maximum length (prevent DoS via bcrypt)
    if len(password) > 128:
        errors.append("Password must be no more than 128 characters long")

    # Character type requirements
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")

    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")

    if not re.search(r'\d', password):
        errors.append("Password must contain at least one number")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)")

    # Common weak patterns
    if _contains_weak_patterns(password):
        errors.append("Password contains common weak patterns (avoid sequences like '123', 'abc', or repeated characters)")

    return len(errors) == 0, errors


def _contains_weak_patterns(password: str) -> bool:
    """Check for common weak patterns in passwords.

    Args:
        password: The password to check.

    Returns:
        bool: True if weak patterns are found, False otherwise.
    """
    password_lower = password.lower()

    # Sequential numbers
    sequential_numbers = [
        "123", "234", "345", "456", "567", "678", "789", "890",
        "012", "321", "432", "543", "654", "765", "876", "987"
    ]

    # Sequential letters
    sequential_letters = [
        "abc", "bcd", "cde", "def", "efg", "fgh", "ghi", "hij", "ijk", "jkl", "klm",
        "lmn", "mno", "nop", "opq", "pqr", "qrs", "rst", "stu", "tuv", "uvw", "vwx",
        "wxy", "xyz", "zyx", "yxw", "xwv", "wvu", "vut", "uts", "tsr", "srq", "rqp",
        "qpo", "pon", "onm", "nml", "mlk", "lkj", "kji", "jih", "ihg", "hgf", "gfe",
        "fed", "edc", "dcb", "cba"
    ]

    # Repeated characters (3+ in a row)
    repeated_pattern = re.compile(r'(.)\1{2,}')

    # Keyboard patterns
    keyboard_patterns = [
        "qwerty", "asdf", "zxcv", "qwertz", "azerty",
        "123456", "654321", "111111", "000000"
    ]

    # Check for patterns
    for pattern in sequential_numbers + sequential_letters + keyboard_patterns:
        if pattern in password_lower:
            return True

    # Check for repeated characters
    if repeated_pattern.search(password):
        return True

    return False


def sanitize_email(email: str) -> str:
    """Sanitize and normalize an email address.

    Args:
        email: Raw email address input.

    Returns:
        str: Normalized email address (lowercase, trimmed).

    Raises:
        ValueError: If email format is invalid.
    """
    if not email:
        raise ValueError("Email address is required")

    # Trim whitespace and convert to lowercase
    normalized = email.strip().lower()

    # Basic email format validation
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    if not email_pattern.match(normalized):
        raise ValueError("Invalid email address format")

    return normalized
