"""
Tests for CV Optimizer Service — Business logic integration tests.

Tests the service layer that coordinates CV optimization, cover letter
generation, and PDF export with database operations.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from app.models.user import User
from app.services.cv_optimizer_service import CVOptimizerService


class TestCVOptimizerService:
    """Test CV optimizer service integration."""

    @pytest.fixture
    def cv_optimizer_service(self):
        """Create CV optimizer service with mocked agent."""
        service = CVOptimizerService()
        service.cv_optimizer = AsyncMock()
        return service

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.full_name = "John Doe"
        user.email = "john@example.com"
        return user

    @pytest.fixture
    def sample_job(self):
        """Sample job for testing."""
        job = Mock(spec=ScrapedJob)
        job.id = uuid.uuid4()
        job.job_title = "Senior Frontend Developer"
        job.company_name = "InnovateTech"
        job.description = "We are looking for an experienced frontend developer..."
        return job

    @pytest.fixture
    def sample_parsed_resume(self):
        """Sample parsed resume for testing."""
        resume = Mock(spec=ParsedResume)
        resume.id = uuid.uuid4()
        resume.user_id = uuid.uuid4()
        resume.is_active = True
        resume.parsed_data = {
            "personal_info": {"full_name": "John Doe"},
            "summary": "Experienced developer",
            "experience": [{"role": "Developer", "company": "TechCorp"}],
            "skills": ["JavaScript", "React", "Python"]
        }
        return resume

    @pytest.fixture
    def sample_user_job(self):
        """Sample UserJob for testing."""
        user_job = Mock(spec=UserJob)
        user_job.id = uuid.uuid4()
        user_job.user_id = uuid.uuid4()
        user_job.job_id = uuid.uuid4()
        user_job.optimized_cv = None
        user_job.cover_letter = None
        user_job.match_score = 75
        user_job.status = "new"
        user_job.updated_at = datetime.now(timezone.utc)
        return user_job

    @pytest.mark.asyncio
    async def test_optimize_cv_for_job_success(
        self, cv_optimizer_service, sample_user, sample_job, sample_parsed_resume, sample_user_job
    ):
        """Test successful CV optimization for a job."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_parsed_resume,  # First call for active resume
            sample_user_job        # Second call for UserJob
        ]

        optimized_cv_data = {
            "summary": "Optimized summary with keywords",
            "experience": [{"role": "Senior Developer", "company": "TechCorp"}],
            "skills": ["React", "TypeScript", "Node.js"]
        }

        cv_optimizer_service.cv_optimizer.optimize_cv_for_job.return_value = optimized_cv_data

        # Execute optimization
        result = await cv_optimizer_service.optimize_cv_for_job(
            user=sample_user,
            job=sample_job,
            db=mock_db
        )

        # Verify AI agent was called
        cv_optimizer_service.cv_optimizer.optimize_cv_for_job.assert_called_once_with(
            parsed_cv=sample_parsed_resume.parsed_data,
            job_description=sample_job.description,
            job_title=sample_job.job_title,
            company_name=sample_job.company_name
        )

        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_user_job)

        # Verify UserJob was updated
        assert sample_user_job.optimized_cv == optimized_cv_data
        assert result == optimized_cv_data

    @pytest.mark.asyncio
    async def test_optimize_cv_no_resume(self, cv_optimizer_service, sample_user, sample_job):
        """Test CV optimization when user has no active resume."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with pytest.raises(ValueError, match="has no active resume"):
            await cv_optimizer_service.optimize_cv_for_job(
                user=sample_user,
                job=sample_job,
                db=mock_db
            )

    @pytest.mark.asyncio
    async def test_optimize_cv_no_user_job(
        self, cv_optimizer_service, sample_user, sample_job, sample_parsed_resume
    ):
        """Test CV optimization when UserJob doesn't exist."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_parsed_resume,  # Active resume found
            None                   # No UserJob found
        ]

        with pytest.raises(ValueError, match="No UserJob record found"):
            await cv_optimizer_service.optimize_cv_for_job(
                user=sample_user,
                job=sample_job,
                db=mock_db
            )

    @pytest.mark.asyncio
    async def test_generate_cover_letter_success(
        self, cv_optimizer_service, sample_user, sample_job, sample_parsed_resume, sample_user_job
    ):
        """Test successful cover letter generation."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_parsed_resume,
            sample_user_job
        ]

        generated_letter = "Dear Hiring Manager, I am excited about this opportunity..."
        cv_optimizer_service.cv_optimizer.generate_cover_letter.return_value = generated_letter

        result = await cv_optimizer_service.generate_cover_letter(
            user=sample_user,
            job=sample_job,
            db=mock_db
        )

        # Verify AI agent was called
        cv_optimizer_service.cv_optimizer.generate_cover_letter.assert_called_once_with(
            parsed_cv=sample_parsed_resume.parsed_data,
            job_description=sample_job.description,
            job_title=sample_job.job_title,
            company_name=sample_job.company_name,
            user_name=sample_user.full_name
        )

        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_user_job)

        # Verify UserJob was updated
        assert sample_user_job.cover_letter == generated_letter
        assert result == generated_letter

    @pytest.mark.asyncio
    @patch("app.services.cv_optimizer_service.pdf_exporter")
    async def test_export_optimized_cv_pdf(
        self, mock_pdf_exporter, cv_optimizer_service, sample_user, sample_user_job
    ):
        """Test CV PDF export."""
        # Setup UserJob with optimized CV
        sample_user_job.optimized_cv = {"summary": "Optimized CV content"}

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user_job

        # Mock PDF export
        pdf_data = b"PDF content here"
        mock_pdf_exporter.export_cv_to_pdf.return_value = pdf_data

        result_pdf, result_filename = await cv_optimizer_service.export_optimized_cv_pdf(
            user=sample_user,
            job_id=str(sample_user_job.job_id),
            db=mock_db
        )

        # Verify PDF exporter was called
        mock_pdf_exporter.export_cv_to_pdf.assert_called_once_with(
            optimized_cv=sample_user_job.optimized_cv,
            user_name=sample_user.full_name
        )

        assert result_pdf == pdf_data
        assert "optimized_cv.pdf" in result_filename

    @pytest.mark.asyncio
    async def test_export_cv_pdf_no_optimized_cv(self, cv_optimizer_service, sample_user):
        """Test CV PDF export when no optimized CV exists."""
        mock_user_job = Mock()
        mock_user_job.optimized_cv = None

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_user_job

        with pytest.raises(ValueError, match="No optimized CV found"):
            await cv_optimizer_service.export_optimized_cv_pdf(
                user=sample_user,
                job_id=str(uuid.uuid4()),
                db=mock_db
            )

    @pytest.mark.asyncio
    @patch("app.services.cv_optimizer_service.pdf_exporter")
    async def test_export_cover_letter_pdf(
        self, mock_pdf_exporter, cv_optimizer_service, sample_user, sample_job, sample_user_job
    ):
        """Test cover letter PDF export."""
        # Setup UserJob with cover letter
        sample_user_job.cover_letter = "Dear Hiring Manager..."

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user_job

        # Mock PDF export
        pdf_data = b"Cover letter PDF content"
        mock_pdf_exporter.export_cover_letter_to_pdf.return_value = pdf_data

        result_pdf, result_filename = await cv_optimizer_service.export_cover_letter_pdf(
            user=sample_user,
            job=sample_job,
            db=mock_db
        )

        # Verify PDF exporter was called
        mock_pdf_exporter.export_cover_letter_to_pdf.assert_called_once_with(
            cover_letter_text=sample_user_job.cover_letter,
            user_name=sample_user.full_name,
            job_title=sample_job.job_title,
            company_name=sample_job.company_name
        )

        assert result_pdf == pdf_data
        assert "cover_letter" in result_filename
        assert sample_job.company_name.replace(" ", "_") in result_filename

    @pytest.mark.asyncio
    async def test_get_optimization_suggestions(
        self, cv_optimizer_service, sample_user, sample_parsed_resume
    ):
        """Test optimization suggestions generation."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_parsed_resume

        suggestions = {
            "keywords_to_add": ["React", "TypeScript"],
            "sections_to_enhance": {"experience": "Add more technical details"},
            "match_score": 75,
            "priority_improvements": ["Update skills section"]
        }

        cv_optimizer_service.cv_optimizer.get_optimization_suggestions.return_value = suggestions

        result = await cv_optimizer_service.get_optimization_suggestions(
            user=sample_user,
            job_description="Frontend developer position requiring React",
            db=mock_db
        )

        # Verify AI agent was called
        cv_optimizer_service.cv_optimizer.get_optimization_suggestions.assert_called_once_with(
            parsed_cv=sample_parsed_resume.parsed_data,
            job_description="Frontend developer position requiring React"
        )

        assert result == suggestions

    @pytest.mark.asyncio
    async def test_get_user_optimized_materials(self, cv_optimizer_service, sample_user):
        """Test retrieving user's optimized materials."""
        # Create sample UserJob with materials
        user_job1 = Mock(spec=UserJob)
        user_job1.id = uuid.uuid4()
        user_job1.job_id = uuid.uuid4()
        user_job1.optimized_cv = {"summary": "Optimized"}
        user_job1.cover_letter = "Dear Hiring Manager..."
        user_job1.match_score = 85
        user_job1.status = "new"
        user_job1.updated_at = datetime.now(timezone.utc)

        user_job2 = Mock(spec=UserJob)
        user_job2.id = uuid.uuid4()
        user_job2.job_id = uuid.uuid4()
        user_job2.optimized_cv = None
        user_job2.cover_letter = "Another cover letter"
        user_job2.match_score = 70
        user_job2.status = "applied"
        user_job2.updated_at = datetime.now(timezone.utc)

        # Mock jobs
        job1 = Mock(spec=ScrapedJob)
        job1.id = user_job1.job_id
        job1.job_title = "Frontend Developer"
        job1.company_name = "TechCorp"

        job2 = Mock(spec=ScrapedJob)
        job2.id = user_job2.job_id
        job2.job_title = "Backend Developer"
        job2.company_name = "DataCorp"

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [user_job1, user_job2]
        mock_db.get.side_effect = [job1, job2]

        result = await cv_optimizer_service.get_user_optimized_materials(
            user=sample_user,
            db=mock_db
        )

        assert len(result) == 2

        # Verify first material
        material1 = result[0]
        assert material1["user_job_id"] == str(user_job1.id)
        assert material1["job_title"] == "Frontend Developer"
        assert material1["company_name"] == "TechCorp"
        assert material1["has_optimized_cv"] is True
        assert material1["has_cover_letter"] is True
        assert material1["match_score"] == 85

        # Verify second material
        material2 = result[1]
        assert material2["has_optimized_cv"] is False
        assert material2["has_cover_letter"] is True
        assert material2["status"] == "applied"

    @pytest.mark.asyncio
    async def test_error_handling_with_rollback(
        self, cv_optimizer_service, sample_user, sample_job, sample_parsed_resume, sample_user_job
    ):
        """Test error handling with database rollback."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_parsed_resume,
            sample_user_job
        ]

        # Mock AI agent to raise exception
        cv_optimizer_service.cv_optimizer.optimize_cv_for_job.side_effect = Exception("AI API error")

        with pytest.raises(Exception, match="AI API error"):
            await cv_optimizer_service.optimize_cv_for_job(
                user=sample_user,
                job=sample_job,
                db=mock_db
            )

        # Verify rollback was called
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initialization."""
        with patch("app.services.cv_optimizer_service.CVOptimizerAgent") as mock_agent_class:
            mock_agent = Mock()
            mock_agent_class.return_value = mock_agent

            service = CVOptimizerService()
            assert service.cv_optimizer == mock_agent

    @pytest.mark.asyncio
    async def test_get_materials_no_job_found(self, cv_optimizer_service, sample_user):
        """Test materials retrieval when job is not found."""
        user_job = Mock(spec=UserJob)
        user_job.id = uuid.uuid4()
        user_job.job_id = uuid.uuid4()
        user_job.optimized_cv = {"summary": "Test"}
        user_job.cover_letter = None

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [user_job]
        mock_db.get.return_value = None  # Job not found

        result = await cv_optimizer_service.get_user_optimized_materials(
            user=sample_user,
            db=mock_db
        )

        # Should skip jobs that can't be found
        assert len(result) == 0