"""
Job Content Hashing Utility — Cross-platform duplicate detection.

Provides utilities for creating content-based hashes of job descriptions
to detect duplicates across different job boards and sources.
"""

import hashlib
import re
from typing import Optional


def create_description_hash(description: Optional[str]) -> str:
    """Create standardized hash of job description for duplicate detection.

    Takes the first 200 characters of job description, normalizes whitespace
    and case, then creates SHA-256 hash for consistent deduplication across
    different job platforms.

    Args:
        description: Job description text (can be None or empty).

    Returns:
        str: SHA-256 hash of normalized description (64 characters).
             Returns hash of empty string if input is None/empty.

    Example:
        >>> hash1 = create_description_hash("Software Engineer at TechCorp...")
        >>> hash2 = create_description_hash("software engineer at techcorp...")
        >>> hash1 == hash2  # True - normalized to same content
    """
    if not description:
        description = ""

    # Take first 200 characters for consistent comparison
    content = description[:200]

    # Normalize content for better duplicate detection:
    # 1. Convert to lowercase
    # 2. Remove extra whitespace and normalize line breaks
    # 3. Remove HTML tags (job boards may include formatting)
    # 4. Remove common job board artifacts
    normalized = content.lower()
    normalized = re.sub(r"<[^>]+>", " ", normalized)  # Remove HTML tags
    normalized = re.sub(r"\s+", " ", normalized)      # Normalize whitespace
    normalized = normalized.strip()

    # Create SHA-256 hash
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_duplicate_by_content(
    description1: Optional[str],
    description2: Optional[str],
) -> bool:
    """Check if two job descriptions are duplicates based on content hash.

    Args:
        description1: First job description.
        description2: Second job description.

    Returns:
        bool: True if descriptions hash to same value (likely duplicates).
    """
    hash1 = create_description_hash(description1)
    hash2 = create_description_hash(description2)
    return hash1 == hash2


def is_duplicate_by_url_or_content(
    url1: Optional[str],
    title1: str,
    company1: str,
    description1: Optional[str],
    url2: Optional[str],
    title2: str,
    company2: str,
    description2: Optional[str],
) -> bool:
    """Advanced duplicate detection using multiple criteria.

    Checks for duplicates using:
    1. Exact URL match (same posting on same platform)
    2. Company + Title + Content hash match (cross-platform duplicates)

    Args:
        url1, url2: Job posting URLs (can be None for internal jobs).
        title1, title2: Job titles.
        company1, company2: Company names.
        description1, description2: Job descriptions.

    Returns:
        bool: True if jobs are likely duplicates.

    Example:
        # Same URL = duplicate
        >>> is_duplicate_by_url_or_content(
        ...     "https://jobs.com/123", "Engineer", "TechCorp", "Description...",
        ...     "https://jobs.com/123", "Engineer", "TechCorp", "Description..."
        ... )
        True

        # Same company + title + description hash = cross-platform duplicate
        >>> is_duplicate_by_url_or_content(
        ...     "https://jobsiteA.com/123", "Engineer", "TechCorp", "We are looking...",
        ...     "https://jobsiteB.com/456", "Engineer", "TechCorp", "We are looking..."
        ... )
        True
    """
    # Check for exact URL match (highest confidence)
    if url1 and url2 and url1 == url2:
        return True

    # Check for company + title + content match (cross-platform duplicates)
    # Normalize company and title for comparison
    company1_norm = company1.lower().strip()
    company2_norm = company2.lower().strip()
    title1_norm = title1.lower().strip()
    title2_norm = title2.lower().strip()

    # Must have same company and similar title
    if company1_norm == company2_norm and title1_norm == title2_norm:
        # Check content hash match
        return is_duplicate_by_content(description1, description2)

    return False


def extract_job_signature(
    title: str,
    company: str,
    description: Optional[str],
) -> str:
    """Extract normalized signature for job comparison.

    Creates a consistent signature combining title, company, and description hash
    for efficient duplicate detection in database queries.

    Args:
        title: Job title.
        company: Company name.
        description: Job description.

    Returns:
        str: Normalized signature for comparison.

    Example:
        >>> signature = extract_job_signature("Software Engineer", "TechCorp", "We are...")
        >>> # Returns: "software engineer|techcorp|abc123def456..."
    """
    title_norm = title.lower().strip()
    company_norm = company.lower().strip()
    desc_hash = create_description_hash(description)

    return f"{title_norm}|{company_norm}|{desc_hash[:16]}"  # First 16 chars of hash