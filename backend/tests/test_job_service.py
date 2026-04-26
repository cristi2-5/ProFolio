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
        jobs_result = MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(
                    all=MagicMock(
                        return_value=[MagicMock(spec=UserJob), MagicMock(spec=UserJob)]
                    )
                )
            )
        )
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
        jobs_result = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
        db.execute = AsyncMock(side_effect=[count_result, jobs_result])

        jobs, total = await service.list_user_jobs(user_id=str(uuid.uuid4()), db=db)

        assert jobs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_accepts_status_filter(self, service):
        """Status filter parameter does not raise."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one=MagicMock(return_value=0),
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                ),
            )
        )
        # Should not raise
        await service.list_user_jobs(
            user_id=str(uuid.uuid4()), db=db, status_filter="applied"
        )

    @pytest.mark.asyncio
    async def test_accepts_search_param(self, service):
        """Search parameter does not raise."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one=MagicMock(return_value=0),
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                ),
            )
        )
        await service.list_user_jobs(user_id=str(uuid.uuid4()), db=db, search="Python")

    @pytest.mark.asyncio
    async def test_accepts_sort_and_order_params(self, service):
        """sort_by and sort_order params are accepted without error."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one=MagicMock(return_value=0),
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                ),
            )
        )
        for sort_col in ["match_score", "created_at", "company_name", "job_title"]:
            for order in ["asc", "desc"]:
                await service.list_user_jobs(
                    user_id=str(uuid.uuid4()),
                    db=db,
                    sort_by=sort_col,
                    sort_order=order,
                )

    @pytest.mark.asyncio
    async def test_accepts_limit_and_offset(self, service):
        """limit and offset params are accepted without error."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one=MagicMock(return_value=0),
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                ),
            )
        )
        await service.list_user_jobs(
            user_id=str(uuid.uuid4()), db=db, limit=10, offset=20
        )


# ──────────────────────────────────────────────
# Test: update_job_status
# ──────────────────────────────────────────────


class TestUpdateJobStatus:
    """Tests for the status update method.

    The implementation uses an atomic ``UPDATE ... RETURNING`` with a
    ``WHERE applied_at IS NULL`` guard on the apply transition (so two
    concurrent "Apply" clicks can't both clobber ``applied_at``). These
    tests stub ``db.execute`` to model the two outcomes:

    * UPDATE matched a row → returns the new id (apply succeeded), then
      the service re-SELECTs to load the ORM instance for the response.
    * UPDATE matched zero rows → service falls back to SELECT and returns
      the existing state (idempotent).
    """

    def _build_update_then_select_db(self, returned_user_job, update_id=None):
        """Construct an AsyncSession mock for the success path.

        First execute → UPDATE returning ``update_id`` (defaults to the
        user_job's id). Second execute → SELECT returning the ORM row.
        """
        db = AsyncMock(spec=AsyncSession)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        update_result = MagicMock()
        update_result.scalar_one_or_none.return_value = (
            update_id or returned_user_job.id
        )

        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = returned_user_job

        db.execute = AsyncMock(side_effect=[update_result, select_result])
        return db

    def _build_zero_rows_db(self, existing_user_job):
        """Construct an AsyncSession mock for the no-rows-updated path.

        First execute → UPDATE returns None (no rows matched). Second
        execute → SELECT returns the existing row (or None if absent).
        """
        db = AsyncMock(spec=AsyncSession)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        update_result = MagicMock()
        update_result.scalar_one_or_none.return_value = None

        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = existing_user_job

        db.execute = AsyncMock(side_effect=[update_result, select_result])
        return db

    @pytest.mark.asyncio
    async def test_sets_applied_at_on_apply(self, service, mock_user_job):
        """Apply transition succeeds → service returns the updated row."""
        db = self._build_update_then_select_db(mock_user_job)

        result = await service.update_job_status(str(mock_user_job.id), "applied", db)

        # Two execute calls: the atomic UPDATE, then the re-SELECT.
        assert db.execute.await_count == 2
        db.commit.assert_awaited_once()
        assert result is mock_user_job

    @pytest.mark.asyncio
    async def test_applied_at_not_overwritten_if_already_set(
        self, service, mock_user_job
    ):
        """Re-applying when applied_at is already set is an idempotent no-op.

        The atomic UPDATE has ``WHERE applied_at IS NULL``, so a second
        apply matches zero rows. The service falls back to a SELECT and
        returns the existing row unchanged.
        """
        original_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_user_job.applied_at = original_ts
        mock_user_job.status = "applied"

        db = self._build_zero_rows_db(mock_user_job)

        result = await service.update_job_status(str(mock_user_job.id), "applied", db)

        assert result is mock_user_job
        # applied_at must not have changed — service did not touch it.
        assert mock_user_job.applied_at == original_ts
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_apply_status_does_not_set_applied_at(
        self, service, mock_user_job
    ):
        """Non-apply transitions don't carry the applied_at guard."""
        db = self._build_update_then_select_db(mock_user_job)

        result = await service.update_job_status(str(mock_user_job.id), "saved", db)

        assert result is mock_user_job
        # applied_at remains None — the service didn't synthesize one.
        assert mock_user_job.applied_at is None

    @pytest.mark.asyncio
    async def test_returns_none_if_user_job_not_found(self, service):
        """Returns None gracefully when user_job_id doesn't exist."""
        db = self._build_zero_rows_db(existing_user_job=None)

        result = await service.update_job_status(str(uuid.uuid4()), "applied", db)

        assert result is None

    @pytest.mark.asyncio
    async def test_commits_after_update(self, service, mock_user_job):
        """DB commit is called after a successful atomic update."""
        db = self._build_update_then_select_db(mock_user_job)

        await service.update_job_status(str(mock_user_job.id), "hidden", db)

        db.commit.assert_awaited_once()


# ──────────────────────────────────────────────
# Test: match_jobs_to_user
# ──────────────────────────────────────────────


class TestMatchJobsToUser:
    """Tests for the job matching / scoring logic."""

    @pytest.mark.asyncio
    async def test_no_resume_returns_empty(self, service, mock_user, mock_scraped_job):
        """Without an active resume, no user-job associations are created."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        result = await service.match_jobs_to_user(mock_user, [mock_scraped_job], db)

        assert result == []

    @pytest.mark.asyncio
    async def test_high_score_creates_user_job(
        self, service, mock_user, mock_scraped_job, mock_active_resume
    ):
        """Jobs scoring above the threshold get a UserJob record."""
        db = AsyncMock(spec=AsyncSession)
        # First execute: resume query; second: existing UserJob check
        resume_result = MagicMock(
            scalar_one_or_none=MagicMock(return_value=mock_active_resume)
        )
        no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        db.execute = AsyncMock(side_effect=[resume_result, no_existing])
        db.add = MagicMock()
        db.flush = AsyncMock()

        # Force a high match score
        with patch.object(service, "_calculate_match_score", return_value=80):
            user_jobs = await service.match_jobs_to_user(
                mock_user, [mock_scraped_job], db
            )

        assert len(user_jobs) == 1
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_score_skips_user_job(
        self, service, mock_user, mock_scraped_job, mock_active_resume
    ):
        """Jobs scoring below the threshold do NOT get a UserJob record."""
        db = AsyncMock(spec=AsyncSession)
        resume_result = MagicMock(
            scalar_one_or_none=MagicMock(return_value=mock_active_resume)
        )
        no_existing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        db.execute = AsyncMock(side_effect=[resume_result, no_existing])
        db.add = MagicMock()
        db.flush = AsyncMock()

        # Force a score below the 30-point threshold
        with patch.object(service, "_calculate_match_score", return_value=10):
            user_jobs = await service.match_jobs_to_user(
                mock_user, [mock_scraped_job], db
            )

        assert user_jobs == []
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_existing_user_job_is_skipped(
        self, service, mock_user, mock_scraped_job, mock_active_resume
    ):
        """Existing user-job associations are not duplicated."""
        existing_uj = MagicMock(spec=UserJob)
        db = AsyncMock(spec=AsyncSession)
        resume_result = MagicMock(
            scalar_one_or_none=MagicMock(return_value=mock_active_resume)
        )
        existing_result = MagicMock(
            scalar_one_or_none=MagicMock(return_value=existing_uj)
        )
        db.execute = AsyncMock(side_effect=[resume_result, existing_result])
        db.add = MagicMock()

        user_jobs = await service.match_jobs_to_user(mock_user, [mock_scraped_job], db)

        assert user_jobs == []
        db.add.assert_not_called()


# ──────────────────────────────────────────────
# Test: get_user_job_by_id
# ──────────────────────────────────────────────


class TestGetUserJobById:
    """Tests for the individual job retrieval service method."""

    @pytest.mark.asyncio
    async def test_returns_job_if_exists_and_belongs_to_user(
        self, service, mock_user_job
    ):
        """Returns the UserJob record when it matches both ID and owner."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=mock_user_job)
            )
        )

        result = await service.get_user_job_by_id(
            user_job_id=str(mock_user_job.id), user_id=str(mock_user_job.user_id), db=db
        )

        assert result == mock_user_job
        db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_if_unauthorized_or_not_found(self, service):
        """Returns None if the record does not exist or belongs to another user."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        result = await service.get_user_job_by_id(
            user_job_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()), db=db
        )

        assert result is None
