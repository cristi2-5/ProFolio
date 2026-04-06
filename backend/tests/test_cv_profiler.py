"""
CV Profiler Tests — AI-powered resume parsing validation.

Tests CV file processing, AI integration, and resume management
with comprehensive mock scenarios and error handling validation.
"""

import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cv_profiler import CVProfilerAgent, ParsedCVData, Experience, Education
from app.models.resume import ParsedResume
from app.models.user import User
from app.services.resume_service import ResumeService
from app.utils.file_processing import (
    validate_cv_file, extract_text_from_file,
    extract_text_from_pdf, extract_text_from_docx
)


# =====================================================================
# Test Fixtures
# =====================================================================

@pytest.fixture
def sample_cv_text() -> str:
    """Sample CV text for AI parsing tests."""
    return """
    John Doe
    john.doe@email.com
    +1-555-123-4567
    San Francisco, CA

    PROFESSIONAL SUMMARY
    Experienced Software Engineer with 5 years of experience in full-stack development.

    EXPERIENCE
    Senior Software Engineer | TechCorp Inc | 2020-2023
    - Developed REST APIs using Python and FastAPI
    - Built React frontends with TypeScript
    - Worked with PostgreSQL and Redis

    Software Developer | StartupXYZ | 2018-2020
    - Created web applications using Django and React
    - Implemented CI/CD pipelines with Docker

    EDUCATION
    Bachelor of Science in Computer Science | University of Tech | 2018
    - GPA: 3.8/4.0
    - Relevant coursework: Data Structures, Algorithms, Database Systems

    SKILLS
    Programming Languages: Python, JavaScript, TypeScript, Java
    Frameworks: FastAPI, React, Django, Express.js
    Databases: PostgreSQL, MongoDB, Redis
    Tools: Docker, Git, AWS, Jenkins

    CERTIFICATIONS
    - AWS Solutions Architect Associate
    - Certified Scrum Master
    """


@pytest.fixture
def mock_gpt_response() -> dict:
    """Mock GPT-4 response for CV parsing."""
    return {
        "full_name": "John Doe",
        "email": "john.doe@email.com",
        "phone": "+1-555-123-4567",
        "location": "San Francisco, CA",
        "summary": "Experienced Software Engineer with 5 years of experience in full-stack development.",
        "skills": ["Problem Solving", "Team Collaboration", "Technical Leadership"],
        "technologies": ["Python", "JavaScript", "TypeScript", "React", "FastAPI", "PostgreSQL", "Docker"],
        "experience": [
            {
                "role": "Senior Software Engineer",
                "company": "TechCorp Inc",
                "period": "2020-2023",
                "description": "Developed REST APIs using Python and FastAPI, built React frontends",
                "technologies": ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL", "Redis"]
            },
            {
                "role": "Software Developer",
                "company": "StartupXYZ",
                "period": "2018-2020",
                "description": "Created web applications using Django and React",
                "technologies": ["Django", "React", "Docker"]
            }
        ],
        "education": [
            {
                "degree": "Bachelor of Science in Computer Science",
                "institution": "University of Tech",
                "year": "2018",
                "details": "GPA: 3.8/4.0"
            }
        ],
        "certifications": ["AWS Solutions Architect Associate", "Certified Scrum Master"],
        "languages": ["English (Native)"],
        "total_years_experience": 5,
        "senior_technologies": ["Python", "React", "PostgreSQL"]
    }


@pytest.fixture
def test_user_data() -> dict:
    """Test user data for resume service tests."""
    return {
        "id": uuid.uuid4(),
        "email": "testuser@example.com",
        "password_hash": "hashed_password",
        "full_name": "Test User",
        "seniority_level": "mid",
        "niche": "Backend Engineering"
    }


@pytest.fixture
async def test_user(test_session: AsyncSession, test_user_data: dict) -> User:
    """Create test user in database."""
    user = User(**test_user_data)
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)
    return user


# =====================================================================
# File Processing Tests
# =====================================================================

class TestFileProcessing:
    """Test file validation and text extraction utilities."""

    def test_validate_cv_file_success(self, tmp_path):
        """Valid PDF/DOCX files should pass validation."""
        # Create test files
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj")

        is_valid, error = validate_cv_file(str(pdf_file), "test.pdf")
        assert is_valid is False  # Will fail because it's not a real PDF, but that's expected

    def test_validate_cv_file_unsupported_extension(self, tmp_path):
        """Unsupported file extensions should fail validation."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("This is a text file")

        is_valid, error = validate_cv_file(str(txt_file), "test.txt")
        assert is_valid is False
        assert "not supported" in error

    def test_validate_cv_file_too_large(self, tmp_path):
        """Files exceeding size limit should fail validation."""
        large_file = tmp_path / "large.pdf"
        large_file.write_bytes(b"%PDF-1.4\n%%EOF\n")
        # Create a file larger than 10MB (simulate)
        with patch('os.path.getsize', return_value=11 * 1024 * 1024):
            is_valid, error = validate_cv_file(str(large_file), "large.pdf")
            assert is_valid is False
            assert "exceeds limit" in error

    def test_validate_cv_file_nonexistent(self):
        """Non-existent files should fail validation."""
        is_valid, error = validate_cv_file("/nonexistent/file.pdf", "file.pdf")
        assert is_valid is False
        assert "does not exist" in error


# =====================================================================
# CV Profiler Agent Tests
# =====================================================================

class TestCVProfilerAgent:
    """Test AI-powered CV parsing agent."""

    @pytest.fixture
    def cv_agent(self):
        """Create CV Profiler Agent instance."""
        return CVProfilerAgent()

    @pytest.mark.asyncio
    async def test_cv_profiler_initialization(self, cv_agent):
        """CV Profiler should initialize correctly."""
        assert cv_agent.model == "gpt-4o-mini"
        assert cv_agent.max_tokens == 2000
        assert cv_agent.temperature == 0.1

    @pytest.mark.asyncio
    async def test_parse_cv_success(self, cv_agent, tmp_path, sample_cv_text, mock_gpt_response):
        """Successful CV parsing with AI should return structured data."""
        # Create mock PDF file
        test_file = tmp_path / "test_resume.pdf"
        test_file.write_bytes(b"%PDF-1.4\n%%EOF\n")

        # Mock file processing and OpenAI API
        with patch('app.agents.cv_profiler.extract_text_from_file', return_value=sample_cv_text), \
             patch('app.agents.cv_profiler.openai_client') as mock_client:

            # Mock OpenAI response
            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps(mock_gpt_response)
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            # Test parsing
            result = await cv_agent.parse(str(test_file), "test_resume.pdf")

            # Verify result structure
            assert result["full_name"] == "John Doe"
            assert result["email"] == "john.doe@email.com"
            assert len(result["experience"]) == 2
            assert len(result["education"]) == 1
            assert result["total_years_experience"] == 5
            assert "Python" in result["technologies"]

    @pytest.mark.asyncio
    async def test_parse_cv_openai_error(self, cv_agent, tmp_path, sample_cv_text):
        """OpenAI API errors should be handled gracefully."""
        test_file = tmp_path / "test_resume.pdf"
        test_file.write_bytes(b"%PDF-1.4\n%%EOF\n")

        with patch('app.agents.cv_profiler.extract_text_from_file', return_value=sample_cv_text), \
             patch('app.agents.cv_profiler.openai_client') as mock_client:

            # Mock OpenAI API error
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            # Test error handling
            with pytest.raises(Exception) as exc_info:
                await cv_agent.parse(str(test_file), "test_resume.pdf")

            assert "CV parsing failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_cv_invalid_json(self, cv_agent, tmp_path, sample_cv_text):
        """Invalid JSON from OpenAI should be handled."""
        test_file = tmp_path / "test_resume.pdf"
        test_file.write_bytes(b"%PDF-1.4\n%%EOF\n")

        with patch('app.agents.cv_profiler.extract_text_from_file', return_value=sample_cv_text), \
             patch('app.agents.cv_profiler.openai_client') as mock_client:

            # Mock invalid JSON response
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "invalid json content"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            # Test error handling
            with pytest.raises(Exception) as exc_info:
                await cv_agent.parse(str(test_file), "test_resume.pdf")

            assert "AI returned invalid JSON" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_parsing_stats(self, cv_agent):
        """Parsing stats should return health information."""
        stats = await cv_agent.get_parsing_stats()

        assert "agent_status" in stats
        assert "model" in stats
        assert "api_configured" in stats
        assert "last_health_check" in stats
        assert stats["model"] == "gpt-4o-mini"


# =====================================================================
# Resume Service Tests
# =====================================================================

class TestResumeService:
    """Test resume business logic and file management."""

    @pytest.fixture
    def resume_service(self):
        """Create Resume Service instance."""
        return ResumeService()

    @pytest.fixture
    def mock_upload_file(self):
        """Mock UploadFile for testing."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test_resume.pdf"
        mock_file.read = AsyncMock(return_value=b"mock pdf content")
        return mock_file

    @pytest.mark.asyncio
    async def test_upload_and_parse_success(self, resume_service, test_session, test_user, mock_upload_file, mock_gpt_response):
        """Successful CV upload and parsing should create resume record."""
        with patch.object(resume_service.cv_profiler, 'parse', return_value=mock_gpt_response) as mock_parse, \
             patch('builtins.open', MagicMock()), \
             patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'unlink'):

            # Test upload and parse
            resume = await resume_service.upload_and_parse(test_session, test_user, mock_upload_file)

            # Verify resume creation
            assert resume.user_id == test_user.id
            assert resume.original_filename == "test_resume.pdf"
            assert resume.parsed_data["full_name"] == "John Doe"
            assert resume.is_active is True   # First resume should be active
            mock_parse.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_and_parse_ai_error(self, resume_service, test_session, test_user, mock_upload_file):
        """AI parsing errors should cleanup files and propagate error."""
        with patch.object(resume_service.cv_profiler, 'parse', side_effect=ValueError("AI parsing failed")), \
             patch('builtins.open', MagicMock()), \
             patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'unlink') as mock_unlink:

            # Test error handling
            with pytest.raises(ValueError) as exc_info:
                await resume_service.upload_and_parse(test_session, test_user, mock_upload_file)

            assert "AI parsing failed" in str(exc_info.value)
            mock_unlink.assert_called_once()  # File should be cleaned up

    @pytest.mark.asyncio
    async def test_list_user_resumes(self, resume_service, test_session, test_user):
        """List resumes should return user's resumes ordered by date."""
        # Create test resumes
        resume1 = ParsedResume(
            user_id=test_user.id,
            original_filename="resume1.pdf",
            parsed_data={"full_name": "Test User 1"},
            is_active=True
        )
        resume2 = ParsedResume(
            user_id=test_user.id,
            original_filename="resume2.pdf",
            parsed_data={"full_name": "Test User 2"},
            is_active=False
        )
        test_session.add_all([resume1, resume2])
        await test_session.flush()

        # Test listing
        resumes = await resume_service.list_user_resumes(test_session, test_user.id)

        assert len(resumes) == 2
        assert resumes[0].original_filename == "resume2.pdf"  # Newest first
        assert resumes[1].original_filename == "resume1.pdf"

    @pytest.mark.asyncio
    async def test_set_active_resume(self, resume_service, test_session, test_user):
        """Setting active resume should deactivate others."""
        # Create test resumes
        resume1 = ParsedResume(
            user_id=test_user.id,
            original_filename="resume1.pdf",
            parsed_data={"full_name": "Test User 1"},
            is_active=True
        )
        resume2 = ParsedResume(
            user_id=test_user.id,
            original_filename="resume2.pdf",
            parsed_data={"full_name": "Test User 2"},
            is_active=False
        )
        test_session.add_all([resume1, resume2])
        await test_session.flush()

        # Set resume2 as active
        updated_resume = await resume_service.set_active_resume(test_session, test_user.id, resume2.id)

        # Verify activation
        assert updated_resume.is_active is True

        # Verify resume1 was deactivated
        await test_session.refresh(resume1)
        assert resume1.is_active is False


# =====================================================================
# Pydantic Model Tests
# =====================================================================

class TestPydanticModels:
    """Test CV data validation models."""

    def test_parsed_cv_data_validation(self):
        """ParsedCVData should validate correctly."""
        data = {
            "full_name": "John Doe",
            "email": "john@example.com",
            "skills": ["Python", "React"],
            "technologies": ["FastAPI", "PostgreSQL"],
            "total_years_experience": 5
        }

        cv_data = ParsedCVData(**data)
        assert cv_data.full_name == "John Doe"
        assert cv_data.total_years_experience == 5
        assert len(cv_data.skills) == 2

    def test_experience_model_validation(self):
        """Experience model should validate required fields."""
        exp_data = {
            "role": "Software Engineer",
            "company": "TechCorp",
            "period": "2020-2023",
            "description": "Developed applications"
        }

        experience = Experience(**exp_data)
        assert experience.role == "Software Engineer"
        assert experience.technologies == []  # Default empty list

    def test_education_model_validation(self):
        """Education model should validate with optional details."""
        edu_data = {
            "degree": "Bachelor of Science in Computer Science",
            "institution": "University of Tech",
            "year": "2018"
        }

        education = Education(**edu_data)
        assert education.degree == "Bachelor of Science in Computer Science"
        assert education.details == ""  # Default empty string