"""
Adzuna API Client — Job discovery and search integration.

Provides async HTTP client for the Adzuna job board API with rate limiting,
error handling, and retry logic. Fetches job listings based on user preferences.
"""

import asyncio
import logging
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AdzunaAPIError(Exception):
    """Custom exception for Adzuna API-related errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class AdzunaClient:
    """Async HTTP client for Adzuna job board API.

    Provides methods for searching jobs with rate limiting, error handling,
    and automatic retries for transient failures.

    Attributes:
        base_url: Adzuna API base URL.
        app_id: Application ID from environment.
        app_key: Application key from environment.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
    """

    def __init__(self):
        """Initialize Adzuna API client with configuration."""
        self.base_url = "https://api.adzuna.com/v1/api/jobs"
        self.app_id = settings.adzuna_app_id
        self.app_key = settings.adzuna_app_key
        self.timeout = 30.0
        self.max_retries = 3

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def search_jobs(
        self,
        query: str,
        location: str = "",
        location_type: str = "remote",
        results_per_page: int = 20,
        page: int = 1,
        max_days_old: int = 7,
    ) -> dict[str, Any]:
        """Search for jobs using Adzuna API.

        Args:
            query: Job search query (title, keywords).
            location: Geographic location (city, country).
            location_type: remote, hybrid, or onsite (filters results).
            results_per_page: Number of results per page (max 50).
            page: Page number (1-indexed).
            max_days_old: Only include jobs posted within this many days.

        Returns:
            dict: Adzuna API response including results array and metadata.

        Raises:
            AdzunaAPIError: If API request fails or returns error.
            ValueError: If API credentials are missing.
        """
        # Validate credentials at call-time (not import-time)
        if not self.app_id or not self.app_key:
            raise ValueError(
                "Adzuna API credentials not configured. "
                "Set ADZUNA_APP_ID and ADZUNA_APP_KEY in your .env file."
            )

        # Build search parameters
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": min(results_per_page, 50),  # Adzuna limit
            "what": query,
            "content-type": "application/json",
            "max_days_old": max_days_old,
        }

        # Add location if specified (empty for remote jobs)
        if location and location_type != "remote":
            params["where"] = location

        # Country code (default to US, can be extended for international)
        country_code = "us"
        endpoint = f"{self.base_url}/{country_code}/search/{page}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.info(
                    f"Searching Adzuna: query='{query}', location_type='{location_type}', page={page}"
                )

                response = await client.get(endpoint, params=params)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        f"Adzuna rate limit exceeded. Retry after {retry_after}s"
                    )
                    await asyncio.sleep(retry_after)
                    raise AdzunaAPIError(
                        f"Rate limit exceeded. Retry after {retry_after}s", 429
                    )

                # Handle API errors
                if response.status_code != 200:
                    error_msg = f"Adzuna API error: {response.status_code}"
                    if response.text:
                        error_msg += f" - {response.text[:200]}"
                    logger.error(error_msg)
                    raise AdzunaAPIError(error_msg, response.status_code)

                data = response.json()

                # Validate response structure
                if "results" not in data:
                    logger.error(
                        f"Invalid Adzuna response structure: {list(data.keys())}"
                    )
                    raise AdzunaAPIError("Invalid API response structure")

                # Log success
                result_count = len(data.get("results", []))
                total_count = data.get("count", 0)
                logger.info(
                    f"Adzuna search successful: {result_count} results (total: {total_count})"
                )

                # Filter by location type for better matching
                if location_type == "remote":
                    data["results"] = self._filter_remote_jobs(data["results"])

                return data

            except httpx.RequestError as e:
                logger.error(f"Adzuna request failed: {e}")
                raise AdzunaAPIError(f"Request failed: {e}")
            except httpx.TimeoutException:
                logger.error("Adzuna request timeout")
                raise AdzunaAPIError("Request timeout")
            except ValueError as e:
                logger.error(f"Adzuna response parsing failed: {e}")
                raise AdzunaAPIError(f"Response parsing failed: {e}")

    def _filter_remote_jobs(self, jobs: list[dict]) -> list[dict]:
        """Filter jobs to prioritize remote positions.

        Args:
            jobs: List of job dictionaries from Adzuna API.

        Returns:
            list: Filtered jobs with remote-friendly positions.
        """
        remote_keywords = [
            "remote",
            "work from home",
            "wfh",
            "telecommute",
            "distributed",
            "virtual",
            "anywhere",
            "home office",
        ]

        remote_jobs = []
        other_jobs = []

        for job in jobs:
            description = (
                job.get("description", "") + " " + job.get("title", "")
            ).lower()
            location = job.get("location", {}).get("display_name", "").lower()

            is_remote = any(
                keyword in description or keyword in location
                for keyword in remote_keywords
            )

            if is_remote:
                remote_jobs.append(job)
            else:
                other_jobs.append(job)

        # Return remote jobs first, then others
        return remote_jobs + other_jobs

    async def get_job_details(self, job_id: str) -> dict[str, Any]:
        """Fetch detailed information for a specific job.

        Args:
            job_id: Adzuna job ID.

        Returns:
            dict: Detailed job information.

        Raises:
            AdzunaAPIError: If job not found or API error.
        """
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
        }

        country_code = "us"
        endpoint = f"{self.base_url}/{country_code}/details/{job_id}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(endpoint, params=params)

                if response.status_code == 404:
                    raise AdzunaAPIError(f"Job {job_id} not found", 404)
                elif response.status_code != 200:
                    raise AdzunaAPIError(
                        f"API error: {response.status_code}", response.status_code
                    )

                return response.json()

            except httpx.RequestError as e:
                raise AdzunaAPIError(f"Request failed: {e}")

    async def health_check(self) -> bool:
        """Check if Adzuna API is accessible with current credentials.

        Returns:
            bool: True if API is accessible, False otherwise.
        """
        try:
            # Perform a minimal search to test connectivity
            result = await self.search_jobs("test", results_per_page=1, page=1)
            return "results" in result
        except Exception as e:
            logger.error(f"Adzuna health check failed: {e}")
            return False


_adzuna_client_instance: AdzunaClient | None = None


def get_adzuna_client() -> AdzunaClient:
    """Return the global AdzunaClient instance (lazy singleton).

    Defers instantiation until first call so the module is safely
    importable even when env vars are not set (e.g. during tests).

    Returns:
        AdzunaClient: The shared client instance.
    """
    global _adzuna_client_instance
    if _adzuna_client_instance is None:
        _adzuna_client_instance = AdzunaClient()
    return _adzuna_client_instance


# Backwards-compatible alias: callers use adzuna_client as a function
# to get the shared instance. e.g. adzuna_client()
adzuna_client = get_adzuna_client
