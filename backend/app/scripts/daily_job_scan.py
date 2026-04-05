"""
Daily Job Scanner — Cron job wrapper for automated job discovery.

Provides command-line interface and cron integration for running
job scans across all users with preferences configured.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.job_scanner import JobScannerAgent
from app.database import get_async_session

# Configure logging for cron environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/autoapply/job_scanner.log', mode='a'),
    ]
)
logger = logging.getLogger(__name__)


async def run_daily_job_scan() -> dict:
    """Execute daily job scan for all users with preferences.

    This is the main entry point for the cron job. It initializes the
    job scanner, runs scans for all users, and returns statistics.

    Returns:
        dict: Scan results including job counts, user statistics, and timing.

    Raises:
        Exception: If critical scan infrastructure fails.
    """
    start_time = datetime.now(timezone.utc)
    logger.info("Starting daily job scan...")

    try:
        # Initialize job scanner
        scanner = JobScannerAgent()

        # Get database session
        async_session = get_async_session()
        async with async_session() as db:
            # Run scan for all users
            total_jobs = await scanner.scan_all_users(db)

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Prepare results
        scan_results = {
            "status": "success",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "total_jobs_discovered": total_jobs,
            "message": f"Daily scan completed: {total_jobs} new jobs discovered"
        }

        logger.info(
            f"Daily job scan completed successfully: "
            f"{total_jobs} jobs in {duration:.2f}s"
        )
        return scan_results

    except Exception as e:
        error_msg = f"Daily job scan failed: {e}"
        logger.error(error_msg, exc_info=True)

        return {
            "status": "failed",
            "start_time": start_time.isoformat(),
            "error": str(e),
            "message": error_msg
        }


async def run_user_scan(user_id: str) -> dict:
    """Execute job scan for a specific user (testing/debugging).

    Args:
        user_id: UUID of the user to scan for.

    Returns:
        dict: Scan results for the specific user.
    """
    logger.info(f"Starting job scan for user: {user_id}")

    try:
        scanner = JobScannerAgent()
        async_session = get_async_session()

        async with async_session() as db:
            new_jobs = await scanner.scan(user_id, db)

        logger.info(f"User scan completed: {len(new_jobs)} new jobs for user {user_id}")
        return {
            "status": "success",
            "user_id": user_id,
            "jobs_discovered": len(new_jobs),
            "jobs": new_jobs,
        }

    except Exception as e:
        error_msg = f"User scan failed for {user_id}: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": "failed",
            "user_id": user_id,
            "error": str(e),
        }


def main():
    """Command-line entry point for job scanner.

    Usage:
        python -m app.scripts.daily_job_scan               # Scan all users (cron)
        python -m app.scripts.daily_job_scan --user UUID   # Scan specific user
        python -m app.scripts.daily_job_scan --help        # Show usage

    Exit codes:
        0: Success
        1: Scan failed or no jobs found
        2: Invalid arguments
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto-Apply Job Scanner — Daily job discovery automation"
    )
    parser.add_argument(
        "--user",
        type=str,
        help="Scan jobs for specific user UUID (for testing/debugging)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.user:
            # Single user scan
            result = asyncio.run(run_user_scan(args.user))
        else:
            # Full daily scan
            result = asyncio.run(run_daily_job_scan())

        # Print results (for cron logging)
        print(f"Scan result: {result}")

        # Set exit code based on success
        if result["status"] == "success":
            jobs_count = result.get("total_jobs_discovered", result.get("jobs_discovered", 0))
            if jobs_count > 0:
                sys.exit(0)  # Success with jobs found
            else:
                logger.info("Scan completed but no new jobs found")
                sys.exit(0)  # Success but no jobs (normal)
        else:
            logger.error(f"Scan failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)  # Failure

    except KeyboardInterrupt:
        logger.info("Job scan interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()