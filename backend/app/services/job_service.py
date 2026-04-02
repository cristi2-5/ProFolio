"""
Job Service — Business logic for job discovery and management.

Handles job deduplication, user-job matching, and status transitions.
Works with the Job Scanner agent for automated discovery.
"""


class JobService:
    """Handles job-related business logic.

    Methods:
        match_jobs_to_user: Score and match new jobs to a user.
        list_user_jobs: Retrieve matched jobs with filtering.
        update_status: Transition job status (new → applied, etc.).
        detect_duplicates: Cross-platform dedup via description_hash.
    """

    # TODO: Implement in Phase 2
    pass
