"""
Tests for Interview Coach Service — Business logic integration tests.

Tests the service layer that coordinates interview preparation generation,
storage, and retrieval with database operations.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from app.models.user import User
from app.services.interview_coach_service import InterviewCoachService


class TestInterviewCoachService:
    """Test interview coach service integration."""

    @pytest.fixture
    def interview_coach_service(self):
        """Create interview coach service with mocked agent."""
        service = InterviewCoachService()
        service.interview_coach = AsyncMock()
        return service

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.full_name = "John Doe"
        user.email = "john@example.com"
        user.seniority_level = "senior"
        return user

    @pytest.fixture
    def sample_job(self):
        """Sample job for testing."""
        job = Mock(spec=ScrapedJob)
        job.id = uuid.uuid4()
        job.job_title = "Senior Full Stack Developer"
        job.company_name = "TechCorp"
        job.description = "We are looking for an experienced full stack developer..."
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
            "skills": ["JavaScript", "React", "Node.js"]
        }
        return resume

    @pytest.fixture
    def sample_user_job(self):
        """Sample UserJob for testing."""
        user_job = Mock(spec=UserJob)
        user_job.id = uuid.uuid4()
        user_job.user_id = uuid.uuid4()
        user_job.job_id = uuid.uuid4()
        user_job.interview_prep = None
        user_job.match_score = 85
        user_job.status = "new"
        user_job.updated_at = datetime.now(timezone.utc)
        return user_job

    @pytest.fixture
    def sample_interview_prep_materials(self):
        """Sample interview prep materials."""
        return {
            "technical_questions": [
                {
                    "question": "How do you optimize React performance?",
                    "difficulty": "intermediate",
                    "topics": ["React", "Performance"],
                    "guidance": "Discuss memoization and code splitting"
                }
            ],
            "behavioral_questions": [
                {
                    "question": "Tell me about a challenging project.",
                    "scenario": "Assessing problem-solving skills",
                    "star_guidance": "Use STAR method",
                    "company_context": "TechCorp values innovation"
                }
            ],
            "company_research": [
                {
                    "topic": "Company Culture",
                    "information": "Innovation-focused culture",
                    "talking_points": ["Innovation", "Growth"],
                    "questions_to_ask": ["What growth opportunities exist?"]
                }
            ],
            "technology_cheat_sheet": [
                {
                    "concept": "React Hooks",
                    "definition": "Functions for state and lifecycle in functional components",
                    "key_points": ["useState", "useEffect"],
                    "practical_example": "const [state, setState] = useState()"
                }
            ],
            "preparation_strategy": {
                "timeline": "2 weeks preparation",
                "focus_areas": ["React", "Node.js"],
                "practice_recommendations": ["Code challenges"],
                "confidence_boosters": ["Review projects"],
                "day_of_tips": ["Arrive early", "Stay calm"]
            }
        }

    @pytest.mark.asyncio
    async def test_generate_interview_prep_materials_success(
        self,
        interview_coach_service,
        sample_user,
        sample_job,
        sample_parsed_resume,
        sample_user_job,
        sample_interview_prep_materials
    ):
        """Test successful interview prep generation."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_parsed_resume,  # Active resume query
            sample_user_job        # UserJob query
        ]

        interview_coach_service.interview_coach.generate_interview_prep_materials.return_value = (
            sample_interview_prep_materials
        )

        # Execute generation
        result = await interview_coach_service.generate_interview_prep_materials(
            user=sample_user,
            job=sample_job,
            db=mock_db,
            include_user_background=True
        )

        # Verify AI agent was called
        interview_coach_service.interview_coach.generate_interview_prep_materials.assert_called_once_with(
            job_description=sample_job.description,
            job_title=sample_job.job_title,
            company_name=sample_job.company_name,
            user_experience_level=sample_user.seniority_level,
            user_background=sample_parsed_resume.parsed_data
        )

        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_user_job)

        # Verify UserJob was updated
        assert sample_user_job.interview_prep == sample_interview_prep_materials
        assert result == sample_interview_prep_materials

    @pytest.mark.asyncio
    async def test_generate_prep_without_background(
        self, interview_coach_service, sample_user, sample_job, sample_user_job, sample_interview_prep_materials
    ):
        """Test prep generation without user background."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            None,  # No active resume
            sample_user_job
        ]

        interview_coach_service.interview_coach.generate_interview_prep_materials.return_value = (
            sample_interview_prep_materials
        )

        result = await interview_coach_service.generate_interview_prep_materials(
            user=sample_user,
            job=sample_job,
            db=mock_db,
            include_user_background=False
        )

        # Should still work without background
        assert result == sample_interview_prep_materials

        # Verify AI agent was called without user_background
        interview_coach_service.interview_coach.generate_interview_prep_materials.assert_called_once_with(
            job_description=sample_job.description,
            job_title=sample_job.job_title,
            company_name=sample_job.company_name,
            user_experience_level=sample_user.seniority_level,
            user_background=None
        )

    @pytest.mark.asyncio
    async def test_generate_prep_no_user_job(
        self, interview_coach_service, sample_user, sample_job, sample_parsed_resume
    ):
        """Test prep generation when UserJob doesn't exist."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_parsed_resume,  # Active resume found
            None                   # No UserJob found
        ]

        with pytest.raises(ValueError, match="No UserJob record found"):
            await interview_coach_service.generate_interview_prep_materials(
                user=sample_user,
                job=sample_job,
                db=mock_db
            )

    @pytest.mark.asyncio
    async def test_get_interview_prep_materials_success(
        self, interview_coach_service, sample_user, sample_user_job, sample_interview_prep_materials
    ):
        """Test successful retrieval of prep materials."""
        sample_user_job.interview_prep = sample_interview_prep_materials

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user_job

        result = await interview_coach_service.get_interview_prep_materials(
            user=sample_user,
            job_id=str(sample_user_job.job_id),
            db=mock_db
        )

        assert result == sample_interview_prep_materials

    @pytest.mark.asyncio
    async def test_get_prep_materials_not_found(
        self, interview_coach_service, sample_user
    ):
        """Test retrieval when no prep materials exist."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with pytest.raises(ValueError, match="No interview prep materials found"):
            await interview_coach_service.get_interview_prep_materials(
                user=sample_user,
                job_id=str(uuid.uuid4()),
                db=mock_db
            )

    @pytest.mark.asyncio
    async def test_update_interview_prep_materials_success(
        self, interview_coach_service, sample_user, sample_user_job, sample_interview_prep_materials
    ):
        """Test successful update of prep materials."""
        sample_user_job.interview_prep = sample_interview_prep_materials.copy()

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user_job

        updates = {
            "user_notes": "Added my own notes",
            "technical_questions": [{"question": "Updated question"}]
        }

        result = await interview_coach_service.update_interview_prep_materials(
            user=sample_user,
            job_id=str(sample_user_job.job_id),
            updated_materials=updates,
            db=mock_db
        )

        # Verify updates were merged
        assert sample_user_job.interview_prep["user_notes"] == "Added my own notes"
        assert sample_user_job.interview_prep["technical_questions"] == [{"question": "Updated question"}]

        # Original fields should be preserved
        assert "behavioral_questions" in sample_user_job.interview_prep

        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_user_job)

    @pytest.mark.asyncio
    async def test_generate_additional_questions_technical(
        self, interview_coach_service, sample_user, sample_job
    ):
        """Test generation of additional technical questions."""
        mock_db = AsyncMock()

        additional_questions = [
            {"question": "Additional technical question 1"},
            {"question": "Additional technical question 2"}
        ]

        interview_coach_service.interview_coach.generate_technical_questions.return_value = additional_questions

        result = await interview_coach_service.generate_additional_questions(
            user=sample_user,
            job=sample_job,
            question_type="technical",
            count=2,
            db=mock_db
        )

        interview_coach_service.interview_coach.generate_technical_questions.assert_called_once_with(
            job_description=sample_job.description,
            job_title=sample_job.job_title,
            user_experience_level=sample_user.seniority_level,
            question_count=2
        )

        assert result["additional_technical_questions"] == additional_questions

    @pytest.mark.asyncio
    async def test_generate_additional_questions_behavioral(
        self, interview_coach_service, sample_user, sample_job
    ):
        """Test generation of additional behavioral questions."""
        mock_db = AsyncMock()

        additional_questions = [
            {"question": "Additional behavioral question"}
        ]

        interview_coach_service.interview_coach.generate_behavioral_questions.return_value = additional_questions

        result = await interview_coach_service.generate_additional_questions(
            user=sample_user,
            job=sample_job,
            question_type="behavioral",
            count=1,
            db=mock_db
        )

        interview_coach_service.interview_coach.generate_behavioral_questions.assert_called_once_with(
            job_description=sample_job.description,
            company_name=sample_job.company_name,
            job_title=sample_job.job_title,
            question_count=1
        )

        assert result["additional_behavioral_questions"] == additional_questions

    @pytest.mark.asyncio
    async def test_generate_additional_questions_company(
        self, interview_coach_service, sample_user, sample_job
    ):
        """Test generation of additional company research questions."""
        mock_db = AsyncMock()

        company_research = [
            {"topic": "Additional company research"}
        ]

        interview_coach_service.interview_coach.generate_company_research.return_value = company_research

        result = await interview_coach_service.generate_additional_questions(
            user=sample_user,
            job=sample_job,
            question_type="company",
            count=1,
            db=mock_db
        )

        interview_coach_service.interview_coach.generate_company_research.assert_called_once_with(
            company_name=sample_job.company_name,
            job_title=sample_job.job_title,
            job_description=sample_job.description
        )

        assert result["additional_company_questions"] == company_research

    @pytest.mark.asyncio
    async def test_generate_additional_questions_invalid_type(
        self, interview_coach_service, sample_user, sample_job
    ):
        """Test generation with invalid question type."""
        mock_db = AsyncMock()

        with pytest.raises(ValueError, match="Invalid question type"):
            await interview_coach_service.generate_additional_questions(
                user=sample_user,
                job=sample_job,
                question_type="invalid",
                count=1,
                db=mock_db
            )

    @pytest.mark.asyncio
    async def test_get_user_interview_preps(
        self, interview_coach_service, sample_user, sample_interview_prep_materials
    ):
        """Test getting all user interview preps."""
        # Create sample UserJob with prep materials
        user_job1 = Mock(spec=UserJob)
        user_job1.id = uuid.uuid4()
        user_job1.job_id = uuid.uuid4()
        user_job1.interview_prep = sample_interview_prep_materials
        user_job1.match_score = 85
        user_job1.status = "new"
        user_job1.updated_at = datetime.now(timezone.utc)

        user_job2 = Mock(spec=UserJob)
        user_job2.id = uuid.uuid4()
        user_job2.job_id = uuid.uuid4()
        user_job2.interview_prep = {"technical_questions": []}  # Partial materials
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

        result = await interview_coach_service.get_user_interview_preps(
            user=sample_user,
            db=mock_db
        )

        assert len(result) == 2

        # Verify first prep summary
        prep1 = result[0]
        assert prep1["user_job_id"] == str(user_job1.id)
        assert prep1["job_title"] == "Frontend Developer"
        assert prep1["company_name"] == "TechCorp"
        assert prep1["has_technical_questions"] is True
        assert prep1["has_behavioral_questions"] is True
        assert prep1["has_company_research"] is True

        # Verify second prep summary
        prep2 = result[1]
        assert prep2["has_technical_questions"] is True
        assert prep2["has_behavioral_questions"] is False
        assert prep2["status"] == "applied"

    @pytest.mark.asyncio
    async def test_error_handling_with_rollback(
        self, interview_coach_service, sample_user, sample_job, sample_parsed_resume, sample_user_job
    ):
        """Test error handling with database rollback."""
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_parsed_resume,
            sample_user_job
        ]

        # Mock AI agent to raise exception
        interview_coach_service.interview_coach.generate_interview_prep_materials.side_effect = Exception("AI API error")

        with pytest.raises(Exception, match="AI API error"):
            await interview_coach_service.generate_interview_prep_materials(
                user=sample_user,
                job=sample_job,
                db=mock_db
            )

        # Verify rollback was called
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initialization."""
        with patch("app.services.interview_coach_service.InterviewCoachAgent") as mock_agent_class:
            mock_agent = Mock()
            mock_agent_class.return_value = mock_agent

            service = InterviewCoachService()
            assert service.interview_coach == mock_agent

    @pytest.mark.asyncio
    async def test_get_preps_no_job_found(self, interview_coach_service, sample_user):
        """Test preps retrieval when job is not found."""
        user_job = Mock(spec=UserJob)
        user_job.id = uuid.uuid4()
        user_job.job_id = uuid.uuid4()
        user_job.interview_prep = {"technical_questions": []}

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [user_job]
        mock_db.get.return_value = None  # Job not found

        result = await interview_coach_service.get_user_interview_preps(
            user=sample_user,
            db=mock_db
        )

        # Should skip jobs that can't be found
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_update_prep_materials_no_existing(
        self, interview_coach_service, sample_user, sample_user_job
    ):
        """Test updating prep materials when none exist."""
        sample_user_job.interview_prep = None

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user_job

        updates = {"user_notes": "New notes"}

        result = await interview_coach_service.update_interview_prep_materials(
            user=sample_user,
            job_id=str(sample_user_job.job_id),
            updated_materials=updates,
            db=mock_db
        )

        # Should create new materials
        assert sample_user_job.interview_prep == {"user_notes": "New notes"}
        assert result == sample_user_job.interview_prep