"""
Job Service Tests — 15 scenarios.

Tests for JobService: list_user_jobs (search/sort/pagination),
update_job_status (applied_at, status transitions), match_jobs_to_user.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from app.models.user import User
from app.services.job_service import JobService


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def service():
    """Return a fresh JobService instance."""
    return JobService()


@pytest.fixture
def mock_user():
    """Return a synthetic User object."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def mock_user_job():
    """Return a synthetic UserJob object in 'new' status."""
    uj = MagicMock(spec=UserJob)
    uj.id = uuid.uuid4()
    uj.user_id = uuid.uuid4()
    uj.job_id = uuid.uuid4()
    uj.status = "new"
    uj.match_score = 72
    uj.applied_at = None
    return uj


@pytest.fixture
def mock_scraped_job():
    """Return a synthetic ScrapedJob object."""
    job = MagicMock(spec=ScrapedJob)
    job.id = uuid.uuid4()
    job.job_title = "Python Engineer"
    job.company_name = "ACME Corp"
    job.description = "FastAPI, PostgreSQL, Docker, remote."
    job.source_platform = "adzuna"
    return job


@pytest.fixture
def mock_active_resume():
    """Return a synthetic ParsedResume with minimal CV data."""
    resume = MagicMock(spec=ParsedResume)
    resume.id = uuid.uuid4()
    resume.is_active = True
    resume.parsed_data = {
        "skills": ["python", "fastapi"],
        "technologies": ["postgresql", "docker"],
        "experience": [{"role": "Backend Developer", "company": "TechCo"}],
        "total_years_experience": 4,
    }
    return resume


# ──────────────────────────────────────────────
# Test: list_user_jobs
# ──────────────────────────────────────────────

class TestListUserJobs:
    """Tests for the paginated job listing method."""

    @pytest.mark.asyncio
    async def test_returns_tuple_of_jobs_and_count(self, service):
        """Result is always a (list, int) tuple."""
        db = AsyncMock(spec=AsyncSession)
        # count query returns 5, paginated query returns 2 jobs
        count_result = MagicMock(scalar_one=MagicMock(return_value=5))
        jobs_result = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
            MagicMock(spec=UserJob), MagicMock(spec=UserJob)
        ]))))
        db.execute = AsyncMock(side_effect=[count_result, jobs_result])

        jobs, total = await service.list_user_jobs(user_id=str(uuid.uuid4()), db=db)

        assert isinstance(jobs, list)
        assert total == 5
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_empty_db_returns_zero_count(self, service):
        """Empty database returns ([], 0)."""
        db = AsyncMock(spec=AsyncSession)
        count_result = MagicMock(scalar_one=MagicMock(return_value=0))
        jobs_result = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        db.execute = AsyncMock(side_effect=[count_result, jobs_result])

        jobs, total = await service.list_user_jobs(user_id=str(uuid.uuid4()), db=db)

        assert jobs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_accepts_status_filter(self, service):
        """Status filter parameter does not raise."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(return_value=MagicMock(
            scalar_one=MagicMock(return_value=0),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ))
        # Should not raise
        await service.list_user_jobs(
            user_id=str(uuid.uuid4()), db=db, status_filter="applied"
        )

    @pytest.mark.asyncio
    async def test_accepts_search_param(self, service):
        """Search parameter does not raise."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(return_value=MagicMock(
            scalar_one=MagicMock(return_value=0),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ))
        await service.list_user_jobs(
            user_id=str(uuid.uuid4()), db=db, search="Python"
        )

    @pytest.mark.asyncio
    async def test_accepts_sort_and_order_params(self, service):
        """sort_by and sort_order params are accepted without error."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(return_value=MagicMock(
            scalar_one=MagicMock(return_value=0),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ))
        for sort_col in ["match_score", "created_at", "company_name", "job_title"]:
            for order in ["asc", "desc"]:
                await service.list_user_jobs(
                    user_id=str(uuid.uuid4()), db=db,
                    sort_by=sort_col, sort_order=order,
                )

    @pytest.mark.asyncio
    async def test_accepts_limit_and_offset(self, service):
        """limit and offset params are accepted without error."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(return_value=MagicMock(
            scalar_one=MagicMock(return_value=0),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ))
        await service.list_user_jobs(
            user_id=str(uuid.uuid4()), db=db, limit=10, offset=20
        )


# ──────────────────────────────────────────────
# Test: update_job_status
# ──────────────────────────────────────────────

class TestUpdateJobStatus:
    """Tests for the status update method."""

    @pytest.mark.asyncio
    async def test_sets_applied_at_on_apply(self, service, mock_user_job):
        """Transitioning to 'applied' sets applied_at timestamp."""
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user_job)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await service.update_job_status(str(mock_user_job.id), "applied", db)

        assert mock_user_job.status == "applied"
        assert mock_user_job.applied_at is not None
        assert isinstance(mock_user_job.applied_at, datetime)

    @pytest.mark.asyncio
    async def test_applied_at_not_overwritten_if_already_set(self, service, mock_user_job):
        """Re-applying does not overwrite an existing applied_at timestamp."""
        original_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_user_job.applied_at = original_ts
        mock_user_job.status = "saved"  # Was saved, now re-applying

        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user_job)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await service.update_job_status(str(mock_user_job.id), "applied", db)

        # applied_at must not have changed
        assert mock_user_job.applied_at == original_ts

    @pytest.mark.asyncio
    async def test_non_apply_status_does_not_set_applied_at(self, service, mock_user_job):
        """Transitioning to 'saved' or 'hidden' does NOT set applied_at."""
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user_job)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await service.update_job_status(str(mock_user_job.id), "saved", db)

        assert mock_user_job.status == "saved"
        assert mock_user_job.applied_at is None

    @pytest.mark.asyncio
    async def test_returns_none_if_user_job_not_found(self, service):
        """Returns None gracefully when user_job_id doesn't exist."""
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=None)

        result = await service.update_job_status(str(uuid.uuid4()), "applied", db)

        assert result is None

    @pytest.mark.asyncio
    async def test_commits_and_refreshes(self, service, mock_user_job):
        """DB commit and refresh are called after update."""
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user_job)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await service.update_job_status(str(mock_user_job.id), "hidden", db)

        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(mock_user_job)


# ──────────────────────────────────────────────
# Test: match_jobs_to_user
# ──────────────────────────────────────────────

class TestMatchJobsToUser:
    """Tests for the job matching / scoring logic."""

    @pytest.mark.asyncio
    async def test_no_resume_returns_empty(self, service, mock_user, mock_scraped_job):
        """Without an active resume, no user-job associations are created."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        result = await service.match_jobs_to_user(mock_user, [mock_scraped_job], db)

        assert result == []

    @pytest.mark.asyncio
    async def test_high_score_creates_user_job(self, service, mock_user, mock_scraped_job, mock_active_resume):
        """Jobs scoring above the threshold get a UserJob record."""
        db = AsyncMock(spec=AsyncSession)
        # First execute: resume query; second: existing UserJob check
        resume_result = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_active_resume))
        no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        db.execute = AsyncMock(side_effect=[resume_result, no_existing])
        db.add = MagicMock()
        db.flush = AsyncMock()

        # Force a high match score
        with patch.object(service, "_calculate_match_score", return_value=80):
            user_jobs = await service.match_jobs_to_user(mock_user, [mock_scraped_job], db)

        assert len(user_jobs) == 1
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_score_skips_user_job(self, service, mock_user, mock_scraped_job, mock_active_resume):
        """Jobs scoring below the threshold do NOT get a UserJob record."""
        db = AsyncMock(spec=AsyncSession)
        resume_result = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_active_resume))
        no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        db.execute = AsyncMock(side_effect=[resume_result, no_existing])
        db.add = MagicMock()
        db.flush = AsyncMock()

        # Force a score below the 30-point threshold
        with patch.object(service, "_calculate_match_score", return_value=10):
            user_jobs = await service.match_jobs_to_user(mock_user, [mock_scraped_job], db)

        assert user_jobs == []
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_existing_user_job_is_skipped(self, service, mock_user, mock_scraped_job, mock_active_resume):
        """Existing user-job associations are not duplicated."""
        existing_uj = MagicMock(spec=UserJob)
        db = AsyncMock(spec=AsyncSession)
        resume_result = MagicMock(scalar_one_or_none=MagicMock(return_value=mock_active_resume))
        existing_result = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_uj))
        db.execute = AsyncMock(side_effect=[resume_result, existing_result])
        db.add = MagicMock()

        user_jobs = await service.match_jobs_to_user(mock_user, [mock_scraped_job], db)

        assert user_jobs == []
        db.add.assert_not_called()
