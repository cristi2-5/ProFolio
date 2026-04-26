"""
Jobs Router Tests — 5 scenarios.

Tests for fetching job details and status management.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.job import ScrapedJob, UserJob
from app.models.user import User


class TestJobsRouter:
    """Tests for the /api/jobs router endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Authenticated user for testing."""
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        return user

    @pytest.fixture
    def mock_scraped_job(self):
        """A sample job found by the scanner."""
        job = MagicMock(spec=ScrapedJob)
        job.id = uuid.uuid4()
        job.job_title = "Cloud Engineer"
        job.company_name = "SkyHigh Systems"
        job.location = "Austin, TX"
        job.salary_min = 120000
        job.salary_max = 180000
        job.job_type = "full_time"
        job.description = "We need a cloud engineer."
        job.external_url = "https://skyhigh.com/1"
        return job

    @pytest.fixture
    def mock_user_job(self, mock_user, mock_scraped_job):
        """A user-job relationship."""
        uj = MagicMock(spec=UserJob)
        uj.id = uuid.uuid4()
        uj.user_id = mock_user.id
        uj.job_id = mock_scraped_job.id
        uj.status = "new"
        uj.match_score = 88
        uj.job = mock_scraped_job
        uj.optimized_cv = None
        uj.cover_letter = None
        uj.interview_prep = None
        uj.applied_at = None
        uj.created_at = MagicMock()
        uj.updated_at = MagicMock()
        return uj

    @pytest.mark.asyncio
    async def test_get_job_by_id_success(self, client, mock_user, mock_user_job):
        """GET /api/jobs/{id} returns 200 and flattened job data."""
        from app.dependencies.auth import get_current_user
        from app.main import app

        # Override the get_current_user dependency
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            with patch(
                "app.routers.jobs.job_service.get_user_job_by_id",
                return_value=mock_user_job,
            ):
                response = await client.get(f"/api/jobs/{mock_user_job.id}")

                assert response.status_code == 200
                data = response.json()
                assert data["id"] == str(mock_user_job.id)
                assert data["job_title"] == "Cloud Engineer"
                assert data["company_name"] == "SkyHigh Systems"
                assert data["match_score"] == 88
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_get_job_by_id_not_found(self, client, mock_user):
        """GET /api/jobs/{id} returns 404 if job doesn't exist or not owned by user."""
        from app.dependencies.auth import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            with patch(
                "app.routers.jobs.job_service.get_user_job_by_id", return_value=None
            ):
                fake_id = str(uuid.uuid4())
                response = await client.get(f"/api/jobs/{fake_id}")

                assert response.status_code == 404
                assert response.json()["detail"] == "Job not found"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_list_jobs_success(self, client, mock_user, mock_user_job):
        """GET /api/jobs/ returns a list of jobs."""
        from app.dependencies.auth import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            with patch(
                "app.routers.jobs.job_service.list_user_jobs",
                return_value=([mock_user_job], 1),
            ):
                response = await client.get("/api/jobs/")

                assert response.status_code == 200
                data = response.json()
                assert data["total_count"] == 1
                assert len(data["jobs"]) == 1
                assert data["jobs"][0]["job_title"] == "Cloud Engineer"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
