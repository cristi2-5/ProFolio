"""
Job Scanner Agent — Automated job discovery via Adzuna API.

Runs as a daily cron job. Fetches jobs matching user preferences,
deduplicates across platforms, and stores new listings.

Job API: Adzuna (selected for free tier, legal compliance, structured JSON).
"""

import logging
import re
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.adzuna import AdzunaAPIError, get_adzuna_client
from app.models.job import ScrapedJob
from app.models.user import JobPreference, User
from app.services.job_service import JobService
from app.utils.hashing import create_description_hash

logger = logging.getLogger(__name__)


# Strip common legal-entity suffixes so "Acme, Inc." and "Acme LLC" dedupe
# to the same normalized form. Word-boundary anchored to avoid eating the
# middle of unrelated tokens (e.g. "Incorporation" stays put — but
# "incorporated" is whitelisted explicitly).
_COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b(inc\.?|incorporated|llc|ltd\.?|limited|corp\.?|corporation|co\.?|company|gmbh|sa|ag|plc|pty\.?)\b",
    flags=re.IGNORECASE,
)


def normalize_company_name(name: Optional[str]) -> str:
    """Normalize a company name for dedup matching.

    Strips legal suffixes (Inc, LLC, Ltd, ...), lower-cases, removes
    punctuation and collapses whitespace. The DB still stores the
    original display value — this is purely for comparison.

    Args:
        name: Raw company name as it appears on the job posting.

    Returns:
        Normalized form suitable for equality comparison; empty string
        if the input is falsy.
    """
    if not name:
        return ""
    name = name.strip().lower()
    name = _COMPANY_SUFFIX_PATTERN.sub("", name)
    # Strip punctuation (anything that isn't word/space) -> single space.
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _fuzzy_lock_key(company_norm: str, title_norm: str) -> int:
    """Stable 63-bit integer key for pg_advisory_xact_lock.

    Keyed on (company_norm, title_norm) so two concurrent inserts of the
    same role serialize through the lock and only one wins the dedup
    check. Python's built-in ``hash()`` is randomized per-process, so we
    use a deterministic SHA-256-derived integer instead.
    """
    import hashlib

    digest = hashlib.sha256(f"{company_norm}|{title_norm}".encode("utf-8")).digest()
    # Postgres advisory locks use signed bigints; mask to 63 bits to stay
    # in the positive range.
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFFFFFFFFFF


def _is_postgres(db: AsyncSession) -> bool:
    """Return True if the bound engine speaks PostgreSQL.

    Advisory locks are a PG-only feature; tests that swap in SQLite
    should silently skip the lock rather than fail.
    """
    try:
        return db.bind.dialect.name == "postgresql"
    except Exception:
        return False


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
        deduplication, and stores new jobs in the database. If the user has
        no preferences set, falls back to a default ``developer`` query so
        the user can still browse jobs (matches will score 0 if no resume).

        Args:
            user_id: UUID of the user to scan for.
            db: Database session for queries and inserts.

        Returns:
            list[dict]: Newly discovered and stored jobs.

        Raises:
            ValueError: If user not found.
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

            # Build search query from preferences (or use defaults if none).
            search_query = self._build_search_query(preferences)
            if preferences is None:
                logger.info(
                    "User %s has no preferences — using default 'developer' query",
                    user_id,
                )
                location_type = "remote"
                location = ""
            else:
                location_type = preferences.location_type
                location = "" if location_type == "remote" else "United States"

            # Search Adzuna API
            try:
                api_client = get_adzuna_client()
                adzuna_response = await api_client.search_jobs(
                    query=search_query,
                    location=location,
                    location_type=location_type,
                    results_per_page=self.max_jobs_per_scan,
                    max_days_old=self.max_days_old,
                )
            except ValueError as e:
                logger.error(f"Adzuna not configured for user {user_id}: {e}")
                return []

            jobs = adzuna_response.get("results", [])
            logger.info(f"Found {len(jobs)} jobs from Adzuna for user {user_id}")

            # Process and deduplicate jobs. Duplicates return None from
            # _process_and_deduplicate_job — but we still want to associate
            # them with the current user via a UserJob row, otherwise a
            # second user searching the same terms would see an empty list.
            new_jobs = []
            scraped_jobs: list[ScrapedJob] = []
            unassociated_duplicates: list[ScrapedJob] = []
            for job_data in jobs:
                try:
                    scraped_job = await self._process_and_deduplicate_job(job_data, db)
                    if scraped_job:
                        scraped_jobs.append(scraped_job)
                        new_jobs.append(
                            {
                                "id": str(scraped_job.id),
                                "company_name": scraped_job.company_name,
                                "job_title": scraped_job.job_title,
                                "location": scraped_job.location,
                                "external_url": scraped_job.external_url,
                            }
                        )
                    else:
                        existing = await self._find_existing_scraped_job(job_data, db)
                        if existing is not None:
                            unassociated_duplicates.append(existing)
                except Exception as e:
                    logger.error(f"Error processing job: {e}")
                    continue

            # Match every job we saw this scan to the user. ``match_jobs_to_user``
            # already no-ops when a UserJob row already exists, so passing the
            # dedup'd duplicates is cheap and catches the "CV uploaded later"
            # case where jobs were scraped before the user had a profile.
            all_jobs = scraped_jobs + unassociated_duplicates
            if all_jobs:
                try:
                    user_jobs = await self.job_service.match_jobs_to_user(
                        user, all_jobs, db
                    )
                    logger.info(
                        f"Created {len(user_jobs)} job matches for user {user_id}"
                    )
                except Exception as e:
                    logger.error(f"Error matching jobs to user {user_id}: {e}")

            await db.commit()
            logger.info(
                f"Scan complete for user {user_id}: {len(new_jobs)} new jobs saved"
            )
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
        company_name = job_data.get("company", {}).get(
            "display_name", "Unknown Company"
        )
        job_title = job_data.get("title", "Unknown Position")
        description = job_data.get("description", "")
        location_data = job_data.get("location", {})
        location = location_data.get("display_name", "") if location_data else ""

        # Create description hash for deduplication
        description_hash = create_description_hash(description)

        # Normalized forms for fuzzy dedup matching. The DB still stores
        # the original ``company_name`` for display; normalization is only
        # used when comparing against existing rows.
        norm_company = normalize_company_name(company_name)
        norm_title = job_title.strip().lower() if job_title else ""

        # Pessimistic lock for the fuzzy-match path. There's no DB-level
        # unique index on (normalized_company, normalized_title), so two
        # concurrent scrapers could otherwise both pass the SELECT and
        # both INSERT. The advisory lock — released automatically at txn
        # end — serializes them. Skip on SQLite (tests).
        if _is_postgres(db):
            lock_key = _fuzzy_lock_key(norm_company, norm_title)
            await db.execute(
                text("SELECT pg_advisory_xact_lock(:k)").bindparams(k=lock_key)
            )

        # Check for existing duplicate by URL (DB-level unique constraint
        # exists on external_url, so this is the cheap fast path).
        if external_url:
            stmt = select(ScrapedJob).where(ScrapedJob.external_url == external_url)
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                logger.debug(f"Duplicate job found by URL: {external_url}")
                return None

        # Check for cross-platform duplicate by content signature.
        # We narrow on the indexed ``description_hash`` first, then filter
        # in Python using normalized company/title — that way "Acme Inc"
        # and "Acme, LLC" cross-platform repostings collapse together.
        stmt = select(ScrapedJob).where(
            ScrapedJob.description_hash == description_hash,
        )
        result = await db.execute(stmt)
        for candidate in result.scalars():
            if (
                normalize_company_name(candidate.company_name) == norm_company
                and (candidate.job_title or "").strip().lower() == norm_title
            ):
                logger.debug(
                    f"Duplicate job found by content: {company_name} - {job_title}"
                )
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
            logger.debug(
                f"Duplicate job detected during save: {company_name} - {job_title}"
            )
            return None

    async def _find_existing_scraped_job(
        self,
        job_data: dict[str, Any],
        db: AsyncSession,
    ) -> Optional[ScrapedJob]:
        """Locate the existing ScrapedJob row a dedup'd job_data refers to.

        ``_process_and_deduplicate_job`` returns ``None`` on dedup — useful
        for "did we insert?" but loses the reference to the existing row
        that match_jobs_to_user still needs to consider.
        """
        external_url = job_data.get("redirect_url")
        if external_url:
            result = await db.execute(
                select(ScrapedJob).where(ScrapedJob.external_url == external_url)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        company_name = job_data.get("company", {}).get(
            "display_name", "Unknown Company"
        )
        job_title = job_data.get("title", "Unknown Position")
        description_hash = create_description_hash(job_data.get("description", ""))
        norm_company = normalize_company_name(company_name)
        norm_title = job_title.strip().lower() if job_title else ""
        result = await db.execute(
            select(ScrapedJob).where(
                ScrapedJob.description_hash == description_hash,
            )
        )
        for candidate in result.scalars():
            if (
                normalize_company_name(candidate.company_name) == norm_company
                and (candidate.job_title or "").strip().lower() == norm_title
            ):
                return candidate
        return None

    def _build_search_query(self, preferences: "JobPreference | None") -> str:
        """Build Adzuna search query from user preferences.

        Uses only the desired title as the search term. Adzuna's ``what``
        parameter applies AND-logic across all words, so appending tech keywords
        (React, TypeScript, etc.) produces zero results — they belong in the
        post-scan match-scoring step, not the initial API query.

        Falls back to ``"developer"`` when the user has no preferences so the
        scan can still proceed (the match step will simply score 0 for users
        without a resume).

        Args:
            preferences: User's job search preferences, or ``None``.

        Returns:
            str: The desired job title, or ``"developer"`` as a fallback.
        """
        if preferences is None or not preferences.desired_title:
            return "developer"
        return preferences.desired_title

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
