"""
Job Scanner Agent — Automated job discovery via Adzuna API.

Runs as a daily cron job. Fetches jobs matching user preferences,
deduplicates across platforms, and stores new listings.

Job API: Adzuna (selected for free tier, legal compliance, structured JSON).
"""

import logging
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.clients.adzuna import get_adzuna_client, AdzunaAPIError
from app.models.job import ScrapedJob
from app.models.user import JobPreference, User
from app.services.job_service import JobService
from app.utils.hashing import create_description_hash

logger = logging.getLogger(__name__)


class JobScannerAgent:
    """Discovers relevant job listings from the Adzuna API.

    Runs on a 24-hour cron schedule. For each active user:
    1. Reads job preferences (title, location, keywords).
    2. Queries Adzuna API with those parameters.
    3. Deduplicates results (URL + company/title/description_hash).
    4. Saves new jobs and creates user-job associations.

    Attributes:
        max_jobs_per_scan: Maximum jobs to fetch per user scan.
        max_days_old: Only include jobs posted within this many days.
    """

    def __init__(self):
        """Initialize Job Scanner with configuration."""
        self.max_jobs_per_scan = 50  # Adzuna API limit per request
        self.max_days_old = 7  # Only recent jobs
        self.job_service = JobService()  # For job-user matching

    async def scan(self, user_id: str, db: AsyncSession) -> list[dict]:
        """Scan for new jobs matching a user's preferences.

        Fetches jobs from Adzuna API based on user preferences, performs
        deduplication, and stores new jobs in the database.

        Args:
            user_id: UUID of the user to scan for.
            db: Database session for queries and inserts.

        Returns:
            list[dict]: Newly discovered and stored jobs.

        Raises:
            ValueError: If user not found or has no preferences.
            AdzunaAPIError: If Adzuna API fails.
        """
        logger.info(f"Starting job scan for user: {user_id}")

        try:
            # Get user and their job preferences
            user = await db.get(User, user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            stmt = select(JobPreference).where(JobPreference.user_id == user.id)
            result = await db.execute(stmt)
            preferences = result.scalar_one_or_none()

            if not preferences:
                logger.warning(f"User {user_id} has no job preferences set")
                return []

            # Build search query from preferences
            search_query = self._build_search_query(preferences)
            location = "" if preferences.location_type == "remote" else "United States"

            # Search Adzuna API
            try:
                api_client = get_adzuna_client()
                adzuna_response = await api_client.search_jobs(
                    query=search_query,
                    location=location,
                    location_type=preferences.location_type,
                    results_per_page=self.max_jobs_per_scan,
                    max_days_old=self.max_days_old,
                )
            except ValueError as e:
                logger.error(f"Adzuna not configured for user {user_id}: {e}")
                return []

            jobs = adzuna_response.get("results", [])
            logger.info(f"Found {len(jobs)} jobs from Adzuna for user {user_id}")

            # Process and deduplicate jobs
            new_jobs = []
            scraped_jobs = []
            for job_data in jobs:
                try:
                    scraped_job = await self._process_and_deduplicate_job(job_data, db)
                    if scraped_job:
                        scraped_jobs.append(scraped_job)
                        new_jobs.append({
                            "id": str(scraped_job.id),
                            "company_name": scraped_job.company_name,
                            "job_title": scraped_job.job_title,
                            "location": scraped_job.location,
                            "external_url": scraped_job.external_url,
                        })
                except Exception as e:
                    logger.error(f"Error processing job: {e}")
                    continue

            # Match new jobs to user and calculate scores
            if scraped_jobs:
                try:
                    user_jobs = await self.job_service.match_jobs_to_user(user, scraped_jobs, db)
                    logger.info(f"Created {len(user_jobs)} job matches for user {user_id}")
                except Exception as e:
                    logger.error(f"Error matching jobs to user {user_id}: {e}")

            await db.commit()
            logger.info(f"Scan complete for user {user_id}: {len(new_jobs)} new jobs saved")
            return new_jobs

        except Exception as e:
            await db.rollback()
            logger.error(f"Job scan failed for user {user_id}: {e}")
            raise

    async def _process_and_deduplicate_job(
        self,
        job_data: dict[str, Any],
        db: AsyncSession,
    ) -> Optional[ScrapedJob]:
        """Process Adzuna job data and check for duplicates.

        Args:
            job_data: Raw job data from Adzuna API.
            db: Database session.

        Returns:
            ScrapedJob | None: Created job if new, None if duplicate.
        """
        # Extract job fields from Adzuna response
        external_url = job_data.get("redirect_url")
        company_name = job_data.get("company", {}).get("display_name", "Unknown Company")
        job_title = job_data.get("title", "Unknown Position")
        description = job_data.get("description", "")
        location_data = job_data.get("location", {})
        location = location_data.get("display_name", "") if location_data else ""

        # Create description hash for deduplication
        description_hash = create_description_hash(description)

        # Check for existing duplicate by URL
        if external_url:
            stmt = select(ScrapedJob).where(ScrapedJob.external_url == external_url)
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                logger.debug(f"Duplicate job found by URL: {external_url}")
                return None

        # Check for cross-platform duplicate by content signature
        stmt = select(ScrapedJob).where(
            ScrapedJob.company_name == company_name,
            ScrapedJob.job_title == job_title,
            ScrapedJob.description_hash == description_hash,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            logger.debug(f"Duplicate job found by content: {company_name} - {job_title}")
            return None

        # Create new job record
        try:
            scraped_job = ScrapedJob(
                external_url=external_url,
                company_name=company_name,
                job_title=job_title,
                description=description,
                description_hash=description_hash,
                location=location,
                source_platform="adzuna",
            )
            db.add(scraped_job)
            await db.flush()  # Get the ID without committing transaction

            logger.debug(f"New job saved: {company_name} - {job_title}")
            return scraped_job

        except IntegrityError as e:
            # Handle race condition where another process created the same job
            await db.rollback()
            logger.debug(f"Duplicate job detected during save: {company_name} - {job_title}")
            return None

    def _build_search_query(self, preferences: JobPreference) -> str:
        """Build Adzuna search query from user preferences.

        Args:
            preferences: User's job search preferences.

        Returns:
            str: Search query combining title and keywords.
        """
        # Start with desired title
        query_parts = [preferences.desired_title]

        # Add keywords if available
        if preferences.keywords:
            # Limit to first 3 keywords to avoid overly restrictive queries
            top_keywords = preferences.keywords[:3]
            query_parts.extend(top_keywords)

        return " ".join(query_parts)

    async def scan_all_users(self, db: AsyncSession) -> int:
        """Run scan for all active users (cron entry point).

        Iterates through all users with job preferences and runs scans
        for each one. Collects statistics and handles individual failures.

        Args:
            db: Database session.

        Returns:
            int: Total number of new jobs discovered across all users.
        """
        logger.info("Starting job scan for all users")

        try:
            # Get all users with job preferences
            stmt = select(User).join(JobPreference).where(JobPreference.id.isnot(None))
            result = await db.execute(stmt)
            users = result.scalars().all()

            if not users:
                logger.info("No users with job preferences found")
                return 0

            total_jobs = 0
            successful_scans = 0
            failed_scans = 0

            for user in users:
                try:
                    new_jobs = await self.scan(str(user.id), db)
                    total_jobs += len(new_jobs)
                    successful_scans += 1

                    logger.info(f"User {user.id}: {len(new_jobs)} new jobs")

                except Exception as e:
                    logger.error(f"Scan failed for user {user.id}: {e}")
                    failed_scans += 1
                    continue

            logger.info(
                f"Scan complete: {total_jobs} total jobs, "
                f"{successful_scans} successful, {failed_scans} failed"
            )
            return total_jobs

        except Exception as e:
            logger.error(f"Batch job scan failed: {e}")
            raise
