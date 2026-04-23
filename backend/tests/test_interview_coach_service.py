"""
Tests for the Interview Coach Service — orchestration layer.

The service coordinates the LLM agent with SQLAlchemy persistence. The
agent is always mocked; the DB session is an AsyncMock so we can assert
commit/rollback behavior without touching Postgres.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from app.models.user import User
from app.services.interview_coach_service import InterviewCoachService


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def service() -> InterviewCoachService:
    """Service instance with a mocked agent."""
    svc = InterviewCoachService()
    svc.interview_coach = AsyncMock()
    return svc


@pytest.fixture
def sample_user() -> User:
    user = Mock(spec=User)
    user.id = uuid.uuid4()
    user.email = "john@example.com"
    user.full_name = "John Doe"
    user.seniority_level = "senior"
    return user


@pytest.fixture
def sample_job() -> ScrapedJob:
    job = Mock(spec=ScrapedJob)
    job.id = uuid.uuid4()
    job.job_title = "Senior Backend Engineer"
    job.company_name = "TechCorp"
    job.description = "Python, FastAPI, PostgreSQL, Docker"
    return job


@pytest.fixture
def sample_resume() -> ParsedResume:
    resume = Mock(spec=ParsedResume)
    resume.id = uuid.uuid4()
    resume.is_active = True
    resume.parsed_data = {"skills": ["Python", "FastAPI"]}
    return resume


@pytest.fixture
def sample_user_job() -> UserJob:
    uj = Mock(spec=UserJob)
    uj.id = uuid.uuid4()
    uj.user_id = uuid.uuid4()
    uj.job_id = uuid.uuid4()
    uj.interview_prep = None
    uj.match_score = 80
    uj.status = "new"
    uj.updated_at = datetime.now(timezone.utc)
    return uj


@pytest.fixture
def bundle() -> dict:
    return {
        "technical_questions": [{"question": "q1"}],
        "behavioral_questions": [{"question": "b1"}],
        "technology_cheat_sheet": [{"concept": "Python"}],
        "extracted_technologies": [{"name": "Python", "category": "languages", "mentions": 1}],
    }


def _db_returning(*rows):
    """Build an AsyncMock session where each execute() yields the next row."""
    db = AsyncMock()
    results = []
    for row in rows:
        r = MagicMock()
        r.scalar_one_or_none.return_value = row
        results.append(r)
    db.execute.side_effect = results
    return db


# ----------------------------------------------------------------------
# generate_interview_prep_materials
# ----------------------------------------------------------------------


class TestGenerate:
    """Behavior of ``generate_interview_prep_materials``."""

    @pytest.mark.asyncio
    async def test_happy_path_with_background(
        self, service, sample_user, sample_job, sample_resume, sample_user_job, bundle
    ) -> None:
        db = _db_returning(sample_resume, sample_user_job)
        service.interview_coach.generate_interview_prep_materials.return_value = bundle

        result = await service.generate_interview_prep_materials(
            user=sample_user, job=sample_job, db=db
        )

        service.interview_coach.generate_interview_prep_materials.assert_awaited_once_with(
            job_description=sample_job.description,
            job_title=sample_job.job_title,
            company_name=sample_job.company_name,
            user_experience_level="senior",
            user_background=sample_resume.parsed_data,
            technical_count=3,
            behavioral_count=2,
        )
        assert "generated_at" in result
        assert result["technical_questions"] == bundle["technical_questions"]
        assert sample_user_job.interview_prep == result
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_background_when_disabled(
        self, service, sample_user, sample_job, sample_user_job, bundle
    ) -> None:
        db = _db_returning(sample_user_job)  # Only UserJob query
        service.interview_coach.generate_interview_prep_materials.return_value = bundle

        await service.generate_interview_prep_materials(
            user=sample_user,
            job=sample_job,
            db=db,
            include_user_background=False,
        )

        call_kwargs = service.interview_coach.generate_interview_prep_materials.await_args.kwargs
        assert call_kwargs["user_background"] is None

    @pytest.mark.asyncio
    async def test_missing_user_job_raises(
        self, service, sample_user, sample_job, sample_resume
    ) -> None:
        db = _db_returning(sample_resume, None)

        with pytest.raises(ValueError, match="No UserJob"):
            await service.generate_interview_prep_materials(
                user=sample_user, job=sample_job, db=db
            )
        db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_agent_error_rolls_back(
        self, service, sample_user, sample_job, sample_resume, sample_user_job
    ) -> None:
        db = _db_returning(sample_resume, sample_user_job)
        service.interview_coach.generate_interview_prep_materials.side_effect = (
            Exception("API down")
        )

        with pytest.raises(Exception, match="API down"):
            await service.generate_interview_prep_materials(
                user=sample_user, job=sample_job, db=db
            )
        db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_count_overrides(
        self, service, sample_user, sample_job, sample_resume, sample_user_job, bundle
    ) -> None:
        db = _db_returning(sample_resume, sample_user_job)
        service.interview_coach.generate_interview_prep_materials.return_value = bundle

        await service.generate_interview_prep_materials(
            user=sample_user,
            job=sample_job,
            db=db,
            technical_count=5,
            behavioral_count=3,
        )
        kwargs = service.interview_coach.generate_interview_prep_materials.await_args.kwargs
        assert kwargs["technical_count"] == 5
        assert kwargs["behavioral_count"] == 3


# ----------------------------------------------------------------------
# get_interview_prep_materials
# ----------------------------------------------------------------------


class TestGet:
    @pytest.mark.asyncio
    async def test_returns_stored_bundle(
        self, service, sample_user, sample_user_job, bundle
    ) -> None:
        sample_user_job.interview_prep = bundle
        db = _db_returning(sample_user_job)

        result = await service.get_interview_prep_materials(
            user=sample_user, job_id=str(sample_user_job.job_id), db=db
        )
        assert result == bundle

    @pytest.mark.asyncio
    async def test_missing_user_job_raises(self, service, sample_user) -> None:
        db = _db_returning(None)

        with pytest.raises(ValueError, match="No interview prep"):
            await service.get_interview_prep_materials(
                user=sample_user, job_id=str(uuid.uuid4()), db=db
            )


# ----------------------------------------------------------------------
# update_interview_prep_materials
# ----------------------------------------------------------------------


class TestUpdate:
    @pytest.mark.asyncio
    async def test_merges_onto_existing_bundle(
        self, service, sample_user, sample_user_job, bundle
    ) -> None:
        sample_user_job.interview_prep = dict(bundle)
        db = _db_returning(sample_user_job)

        updates = {"user_notes": "my notes"}
        result = await service.update_interview_prep_materials(
            user=sample_user,
            job_id=str(sample_user_job.job_id),
            updated_materials=updates,
            db=db,
        )

        assert result["user_notes"] == "my notes"
        assert "technical_questions" in result  # preserved
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_creates_bundle_when_none_exists(
        self, service, sample_user, sample_user_job
    ) -> None:
        sample_user_job.interview_prep = None
        db = _db_returning(sample_user_job)

        result = await service.update_interview_prep_materials(
            user=sample_user,
            job_id=str(sample_user_job.job_id),
            updated_materials={"user_notes": "note"},
            db=db,
        )
        assert result == {"user_notes": "note"}


# ----------------------------------------------------------------------
# get_user_interview_preps
# ----------------------------------------------------------------------


class TestListUserPreps:
    @pytest.mark.asyncio
    async def test_summarises_prep_flags(
        self, service, sample_user, bundle
    ) -> None:
        job = Mock(spec=ScrapedJob)
        job.id = uuid.uuid4()
        job.job_title = "Backend Engineer"
        job.company_name = "TechCorp"

        uj = Mock(spec=UserJob)
        uj.id = uuid.uuid4()
        uj.job_id = job.id
        uj.job = job  # selectinload(UserJob.job) — relationship is eager-loaded
        uj.interview_prep = bundle
        uj.match_score = 85
        uj.status = "new"
        uj.updated_at = datetime.now(timezone.utc)

        db = AsyncMock()
        scalars = MagicMock()
        scalars.all.return_value = [uj]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        db.execute.return_value = execute_result

        result = await service.get_user_interview_preps(user=sample_user, db=db)
        assert len(result) == 1
        summary = result[0]
        assert summary["job_title"] == "Backend Engineer"
        assert summary["has_technical_questions"] is True
        assert summary["has_behavioral_questions"] is True
        assert summary["has_cheat_sheet"] is True

    @pytest.mark.asyncio
    async def test_skips_missing_jobs(self, service, sample_user) -> None:
        uj = Mock(spec=UserJob)
        uj.id = uuid.uuid4()
        uj.job_id = uuid.uuid4()
        uj.job = None  # relationship loaded but the row is gone
        uj.interview_prep = {"technical_questions": []}
        uj.match_score = 0
        uj.status = "new"
        uj.updated_at = datetime.now(timezone.utc)

        db = AsyncMock()
        scalars = MagicMock()
        scalars.all.return_value = [uj]
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        db.execute.return_value = execute_result

        result = await service.get_user_interview_preps(user=sample_user, db=db)
        assert result == []


# ----------------------------------------------------------------------
# Initialisation
# ----------------------------------------------------------------------


class TestInit:
    @pytest.mark.asyncio
    async def test_constructs_real_agent_by_default(self) -> None:
        with patch(
            "app.services.interview_coach_service.InterviewCoachAgent"
        ) as agent_cls:
            agent_cls.return_value = Mock()
            svc = InterviewCoachService()
            assert svc.interview_coach is agent_cls.return_value
