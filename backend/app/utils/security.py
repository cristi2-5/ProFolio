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

# Bcrypt context for password hashing with explicit configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Secure but not excessive
    bcrypt__ident="2b"  # Standard bcrypt identifier
)


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Args:
        password: The plain-text password to hash.

    Returns:
        str: The bcrypt hash string.
    """
    try:
        # Workaround for bcrypt version compatibility issue
        # Manually truncate to 72 bytes to prevent the error
        if len(password.encode('utf-8')) > 72:
            password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')

        return pwd_context.hash(password)
    except Exception as e:
        # If bcrypt fails, try fallback approach
        try:
            import bcrypt
            salt = bcrypt.gensalt()
            return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        except Exception as e2:
            raise Exception(f"Password hashing failed: {e}")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash.

    Args:
        plain_password: The plain-text password to check.
        hashed_password: The stored bcrypt hash.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        # Fallback to direct bcrypt
        try:
            import bcrypt
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception as e2:
            return False


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

    Implements reasonable password requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number OR special character (more flexible)
    - Basic weak pattern checking (only obvious ones)

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
    if len(password) > 72:  # bcrypt actual limit
        errors.append("Password must be no more than 72 characters long")

    # Character type requirements
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")

    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")

    # Require either a number OR special character (more flexible)
    has_number = bool(re.search(r'\d', password))
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))

    if not (has_number or has_special):
        errors.append("Password must contain at least one number or special character")

    # Only check for obvious weak patterns
    if _contains_obvious_weak_patterns(password):
        errors.append("Password contains weak patterns (avoid simple sequences like '123456' or 'password')")

    return len(errors) == 0, errors


def _contains_obvious_weak_patterns(password: str) -> bool:
    """Check for only the most obvious weak patterns in passwords.

    Args:
        password: The password to check.

    Returns:
        bool: True if obvious weak patterns are found, False otherwise.
    """
    password_lower = password.lower()

    # Only check for very obvious weak patterns
    obvious_weak_patterns = [
        "123456", "654321", "password", "123123", "qwerty", "111111", "000000",
        "abcdef", "fedcba", "123abc", "abc123"
    ]

    # Check for repeated characters (4+ in a row, not 3)
    repeated_pattern = re.compile(r'(.)\1{3,}')

    # Check obvious patterns
    for pattern in obvious_weak_patterns:
        if pattern in password_lower:
            return True

    # Check for 4+ repeated characters
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
