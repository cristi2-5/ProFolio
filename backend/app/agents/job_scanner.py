"""
Job Scanner Agent — Automated job discovery via Adzuna API.

Runs as a daily cron job. Fetches jobs matching user preferences,
deduplicates across platforms, and stores new listings.

Job API: Adzuna (selected for free tier, legal compliance, structured JSON).
"""

import logging

logger = logging.getLogger(__name__)


class JobScannerAgent:
    """Discovers relevant job listings from the Adzuna API.

    Runs on a 24-hour cron schedule. For each active user:
    1. Reads job preferences (title, location, keywords).
    2. Queries Adzuna API with those parameters.
    3. Deduplicates results (URL + company/title/description_hash).
    4. Saves new jobs and creates user-job associations.
    """

    async def scan(self, user_id: str) -> list[dict]:
        """Scan for new jobs matching a user's preferences.

        Args:
            user_id: UUID of the user to scan for.

        Returns:
            list[dict]: Newly discovered jobs.
        """
        # TODO: Implement in Phase 2
        logger.info("JobScannerAgent.scan called for user: %s", user_id)
        return []

    async def scan_all_users(self) -> int:
        """Run scan for all active users (cron entry point).

        Returns:
            int: Total number of new jobs discovered across all users.
        """
        # TODO: Implement in Phase 2 (cron integration)
        logger.info("JobScannerAgent.scan_all_users triggered")
        return 0
