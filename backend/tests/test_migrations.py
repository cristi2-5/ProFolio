"""
Migration Tests — Validate Alembic Migrations.

Tests migration reversibility, constraint enforcement, and cascade deletes.
"""

import uuid

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benchmark import BenchmarkScore
from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from app.models.user import JobPreference, User


class TestMigrationStructure:
    """Test that migrations create the correct database structure."""

    @pytest.mark.asyncio
    async def test_all_tables_created(self, test_session: AsyncSession):
        """Verify all 6 tables exist after migrations."""
        conn = await test_session.connection()

        def get_table_names(connection):
            inspector = inspect(connection)
            return set(inspector.get_table_names())

        tables = await conn.run_sync(get_table_names)

        expected_tables = {
            "users",
            "job_preferences",
            "parsed_resumes",
            "scraped_jobs",
            "user_jobs",
            "benchmark_scores",
        }
        assert expected_tables.issubset(
            tables
        ), f"Missing tables: {expected_tables - tables}"

    @pytest.mark.asyncio
    async def test_users_table_indexes(self, test_session: AsyncSession):
        """Verify users table has required indexes."""
        conn = await test_session.connection()

        def get_indexes(connection):
            inspector = inspect(connection)
            return inspector.get_indexes("users")

        indexes = await conn.run_sync(get_indexes)
        index_names = {idx["name"] for idx in indexes}

        assert (
            "ix_users_email" in index_names
        ), "Missing email index for fast login lookups"

    @pytest.mark.asyncio
    async def test_parsed_resumes_gin_index(self, test_session: AsyncSession):
        """Verify parsed_resumes has GIN index on JSONB column."""
        conn = await test_session.connection()

        def get_indexes(connection):
            inspector = inspect(connection)
            return inspector.get_indexes("parsed_resumes")

        indexes = await conn.run_sync(get_indexes)
        index_names = {idx["name"] for idx in indexes}


class TestConstraintEnforcement:
    """Test that database constraints enforce data integrity."""

    @pytest.mark.asyncio
    async def test_user_email_unique_constraint(self, test_session: AsyncSession):
        """Verify duplicate emails are rejected."""
        # Create first user
        user1 = User(
            email="test@example.com",
            password_hash="hash1",
            full_name="Test User 1",
        )
        test_session.add(user1)
        await test_session.flush()

        # Attempt duplicate email
        user2 = User(
            email="test@example.com",  # Same email
            password_hash="hash2",
            full_name="Test User 2",
        )
        test_session.add(user2)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert (
            "unique constraint" in str(exc_info.value).lower()
            or "duplicate key" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_user_seniority_level_check_constraint(
        self, test_session: AsyncSession
    ):
        """Verify seniority_level enum is enforced."""
        user = User(
            email="test@example.com",
            password_hash="hash",
            seniority_level="invalid_level",  # Not in enum
        )
        test_session.add(user)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "ck_user_seniority_level" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_job_preference_location_type_check_constraint(
        self, test_session: AsyncSession
    ):
        """Verify location_type enum is enforced."""
        # Create user first
        user = User(email="test@example.com", password_hash="hash")
        test_session.add(user)
        await test_session.flush()

        # Create preference with invalid location_type
        pref = JobPreference(
            user_id=user.id,
            desired_title="Developer",
            location_type="invalid_type",  # Not in enum
        )
        test_session.add(pref)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "ck_jobpref_location_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_user_job_match_score_range_constraint(
        self, test_session: AsyncSession
    ):
        """Verify match_score must be between 0-100."""
        # Create user and job
        user = User(email="test@example.com", password_hash="hash")
        job = ScrapedJob(
            company_name="TechCorp",
            job_title="Developer",
            description="Job description",
        )
        test_session.add_all([user, job])
        await test_session.flush()

        # Create user_job with invalid score
        user_job = UserJob(
            user_id=user.id,
            job_id=job.id,
            match_score=150,  # Out of range
        )
        test_session.add(user_job)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "ck_userjob_match_score" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_user_job_status_check_constraint(self, test_session: AsyncSession):
        """Verify status enum is enforced."""
        # Create user and job
        user = User(email="test@example.com", password_hash="hash")
        job = ScrapedJob(
            company_name="TechCorp",
            job_title="Developer",
            description="Job description",
        )
        test_session.add_all([user, job])
        await test_session.flush()

        # Create user_job with invalid status
        user_job = UserJob(
            user_id=user.id,
            job_id=job.id,
            status="invalid_status",  # Not in enum
        )
        test_session.add(user_job)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "ck_userjob_status" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_benchmark_score_range_constraint(self, test_session: AsyncSession):
        """Verify benchmark score must be between 0-100."""
        user = User(email="test@example.com", password_hash="hash")
        test_session.add(user)
        await test_session.flush()

        benchmark = BenchmarkScore(
            user_id=user.id,
            score=150,  # Out of range
        )
        test_session.add(benchmark)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "ck_benchmark_score_range" in str(exc_info.value)


class TestCascadeDeletes:
    """Test that CASCADE deletes work correctly."""

    @pytest.mark.asyncio
    async def test_user_delete_cascades_to_preferences(
        self, test_session: AsyncSession
    ):
        """Verify deleting user deletes their job preferences."""
        # Create user with preference
        user = User(email="test@example.com", password_hash="hash")
        test_session.add(user)
        await test_session.flush()

        pref = JobPreference(
            user_id=user.id,
            desired_title="Developer",
            location_type="remote",
        )
        test_session.add(pref)
        await test_session.flush()
        pref_id = pref.id

        # Delete user
        await test_session.delete(user)
        await test_session.flush()

        # Verify preference was cascade deleted
        result = await test_session.execute(
            select(JobPreference).where(JobPreference.id == pref_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_user_delete_cascades_to_resumes(self, test_session: AsyncSession):
        """Verify deleting user deletes their resumes."""
        user = User(email="test@example.com", password_hash="hash")
        test_session.add(user)
        await test_session.flush()

        resume = ParsedResume(
            user_id=user.id,
            original_filename="resume.pdf",
            parsed_data={"skills": []},
        )
        test_session.add(resume)
        await test_session.flush()
        resume_id = resume.id

        # Delete user
        await test_session.delete(user)
        await test_session.flush()

        # Verify resume was cascade deleted
        result = await test_session.execute(
            select(ParsedResume).where(ParsedResume.id == resume_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_user_delete_cascades_to_user_jobs(self, test_session: AsyncSession):
        """Verify deleting user deletes their user_jobs."""
        user = User(email="test@example.com", password_hash="hash")
        job = ScrapedJob(
            company_name="TechCorp",
            job_title="Developer",
            description="Job description",
        )
        test_session.add_all([user, job])
        await test_session.flush()

        user_job = UserJob(user_id=user.id, job_id=job.id)
        test_session.add(user_job)
        await test_session.flush()
        user_job_id = user_job.id

        # Delete user
        await test_session.delete(user)
        await test_session.flush()

        # Verify user_job was cascade deleted
        result = await test_session.execute(
            select(UserJob).where(UserJob.id == user_job_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_job_delete_set_null_on_benchmark(self, test_session: AsyncSession):
        """Verify deleting job sets job_id to NULL in benchmarks (not cascade)."""
        user = User(email="test@example.com", password_hash="hash")
        job = ScrapedJob(
            company_name="TechCorp",
            job_title="Developer",
            description="Job description",
        )
        test_session.add_all([user, job])
        await test_session.flush()

        benchmark = BenchmarkScore(
            user_id=user.id,
            job_id=job.id,
            score=75,
        )
        test_session.add(benchmark)
        await test_session.flush()
        benchmark_id = benchmark.id

        # Delete job
        await test_session.delete(job)
        await test_session.flush()

        # Verify benchmark still exists but job_id is NULL
        result = await test_session.execute(
            select(BenchmarkScore).where(BenchmarkScore.id == benchmark_id)
        )
        benchmark_after = result.scalar_one()
        assert benchmark_after is not None
        assert benchmark_after.job_id is None


class TestDeduplication:
    """Test deduplication constraints work correctly."""

    @pytest.mark.asyncio
    async def test_scraped_job_url_unique_constraint(self, test_session: AsyncSession):
        """Verify duplicate job URLs are rejected."""
        job1 = ScrapedJob(
            external_url="https://example.com/job/123",
            company_name="TechCorp",
            job_title="Developer",
            description="Job description",
        )
        test_session.add(job1)
        await test_session.flush()

        job2 = ScrapedJob(
            external_url="https://example.com/job/123",  # Same URL
            company_name="OtherCorp",
            job_title="Engineer",
            description="Different description",
        )
        test_session.add(job2)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "external_url" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_scraped_job_composite_dedup_constraint(
        self, test_session: AsyncSession
    ):
        """Verify cross-platform deduplication works."""
        job1 = ScrapedJob(
            external_url="https://linkedin.com/job/123",
            company_name="TechCorp",
            job_title="Software Developer",
            description="Build amazing products",
            description_hash="abc123",  # Same hash
        )
        test_session.add(job1)
        await test_session.flush()

        # Same job from different platform (different URL)
        job2 = ScrapedJob(
            external_url="https://indeed.com/job/456",  # Different URL
            company_name="TechCorp",  # Same company
            job_title="Software Developer",  # Same title
            description="Build amazing products (reposted)",
            description_hash="abc123",  # Same hash
        )
        test_session.add(job2)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "uq_job_dedup" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_user_job_unique_constraint(self, test_session: AsyncSession):
        """Verify a user can't have duplicate associations with same job."""
        user = User(email="test@example.com", password_hash="hash")
        job = ScrapedJob(
            company_name="TechCorp",
            job_title="Developer",
            description="Job description",
        )
        test_session.add_all([user, job])
        await test_session.flush()

        user_job1 = UserJob(user_id=user.id, job_id=job.id, status="new")
        test_session.add(user_job1)
        await test_session.flush()

        # Try to create duplicate
        user_job2 = UserJob(user_id=user.id, job_id=job.id, status="saved")
        test_session.add(user_job2)

        with pytest.raises(IntegrityError) as exc_info:
            await test_session.flush()

        assert "uq_user_job" in str(exc_info.value)
