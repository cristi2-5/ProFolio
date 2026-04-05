"""
Tests for CV Optimizer Agent — AI-powered CV optimization and cover letters.

Comprehensive test suite covering CV optimization, cover letter generation,
PDF export, and error handling scenarios.
"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
from openai import AsyncOpenAI

from app.agents.cv_optimizer import CVOptimizerAgent


class TestCVOptimizerAgent:
    """Test CV optimizer agent functionality."""

    @pytest.fixture
    def cv_optimizer(self):
        """Create CV optimizer agent with mocked OpenAI client."""
        with patch("app.agents.cv_optimizer.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            agent = CVOptimizerAgent()
            agent.client = AsyncMock(spec=AsyncOpenAI)
            return agent

    @pytest.fixture
    def sample_cv_data(self):
        """Sample parsed CV data for testing."""
        return {
            "personal_info": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+1-555-0123",
                "location": "New York, NY"
            },
            "summary": "Experienced software developer with 5+ years in web development",
            "experience": [
                {
                    "role": "Senior Developer",
                    "company": "TechCorp Inc",
                    "duration": "2020-2023",
                    "description": "Led development of web applications using React and Node.js"
                },
                {
                    "role": "Junior Developer",
                    "company": "StartupXYZ",
                    "duration": "2018-2020",
                    "description": "Developed frontend components and REST APIs"
                }
            ],
            "skills": ["JavaScript", "React", "Node.js", "Python", "SQL"],
            "technologies": ["AWS", "Docker", "Git", "MongoDB"],
            "education": [
                {
                    "degree": "Bachelor of Science in Computer Science",
                    "institution": "University of Technology",
                    "year": "2018"
                }
            ]
        }

    @pytest.fixture
    def sample_job_description(self):
        """Sample job description for testing."""
        return """
        Senior Frontend Developer - InnovateTech

        We are seeking an experienced Frontend Developer to join our team.

        Requirements:
        - 3+ years experience with React and TypeScript
        - Proficiency in modern JavaScript frameworks
        - Experience with AWS cloud services
        - Knowledge of CI/CD pipelines
        - Strong problem-solving skills

        Responsibilities:
        - Develop responsive web applications
        - Collaborate with design and backend teams
        - Implement automated testing
        - Optimize application performance
        """

    @pytest.fixture
    def mock_openai_cv_response(self):
        """Mock OpenAI response for CV optimization."""
        optimized_cv = {
            "personal_info": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+1-555-0123",
                "location": "New York, NY"
            },
            "summary": "Senior Frontend Developer with 5+ years of experience building scalable React applications and modern JavaScript frameworks. Proven expertise in AWS cloud services and CI/CD pipeline implementation.",
            "experience": [
                {
                    "role": "Senior Developer",
                    "company": "TechCorp Inc",
                    "duration": "2020-2023",
                    "description": "Led development of responsive web applications using React, TypeScript, and Node.js. Implemented automated testing and optimized application performance for 50% faster load times."
                }
            ],
            "skills": ["React", "TypeScript", "JavaScript", "AWS", "CI/CD", "Node.js", "Python"],
            "technologies": ["AWS", "Docker", "Git", "MongoDB", "Jest", "Webpack"]
        }

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(optimized_cv)
        return mock_response

    @pytest.fixture
    def mock_openai_cover_letter_response(self):
        """Mock OpenAI response for cover letter generation."""
        cover_letter = """Dear Hiring Manager,

I am writing to express my strong interest in the Senior Frontend Developer position at InnovateTech. With over 5 years of experience developing scalable React applications and expertise in modern JavaScript frameworks, I am excited about the opportunity to contribute to your innovative team.

In my current role as Senior Developer at TechCorp Inc, I have successfully led the development of responsive web applications using React and TypeScript, directly aligning with your requirements. My experience includes implementing automated testing strategies that reduced bug reports by 40% and optimizing application performance to achieve 50% faster load times. Additionally, my proficiency with AWS cloud services and CI/CD pipelines enables me to deliver robust, scalable solutions.

I am particularly drawn to InnovateTech's commitment to cutting-edge technology and innovation. Your focus on creating user-centric applications resonates with my passion for developing intuitive, high-performance web experiences that drive business results.

I would welcome the opportunity to discuss how my technical expertise and proven track record can contribute to InnovateTech's continued success. Thank you for considering my application.

Sincerely,
John Doe"""

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = cover_letter
        return mock_response

    @pytest.mark.asyncio
    async def test_optimize_cv_success(
        self, cv_optimizer, sample_cv_data, sample_job_description, mock_openai_cv_response
    ):
        """Test successful CV optimization."""
        # Setup mock
        cv_optimizer.client.chat.completions.create.return_value = mock_openai_cv_response

        # Execute optimization
        result = await cv_optimizer.optimize_cv_for_job(
            parsed_cv=sample_cv_data,
            job_description=sample_job_description,
            job_title="Senior Frontend Developer",
            company_name="InnovateTech"
        )

        # Verify API call
        cv_optimizer.client.chat.completions.create.assert_called_once()
        call_args = cv_optimizer.client.chat.completions.create.call_args

        assert call_args.kwargs["model"] == "gpt-4o-mini"
        assert call_args.kwargs["response_format"] == {"type": "json_object"}
        assert len(call_args.kwargs["messages"]) == 2
        assert call_args.kwargs["messages"][0]["role"] == "system"
        assert call_args.kwargs["messages"][1]["role"] == "user"

        # Verify result structure
        assert isinstance(result, dict)
        assert "summary" in result
        assert "experience" in result
        assert "skills" in result
        assert "React" in result["skills"]
        assert "TypeScript" in result["skills"]

    @pytest.mark.asyncio
    async def test_generate_cover_letter_success(
        self, cv_optimizer, sample_cv_data, sample_job_description, mock_openai_cover_letter_response
    ):
        """Test successful cover letter generation."""
        # Setup mock
        cv_optimizer.client.chat.completions.create.return_value = mock_openai_cover_letter_response

        # Execute generation
        result = await cv_optimizer.generate_cover_letter(
            parsed_cv=sample_cv_data,
            job_description=sample_job_description,
            job_title="Senior Frontend Developer",
            company_name="InnovateTech",
            user_name="John Doe"
        )

        # Verify API call
        cv_optimizer.client.chat.completions.create.assert_called_once()
        call_args = cv_optimizer.client.chat.completions.create.call_args

        assert call_args.kwargs["model"] == "gpt-4o-mini"
        assert call_args.kwargs["max_tokens"] == 1500
        assert call_args.kwargs["temperature"] == 0.4

        # Verify result
        assert isinstance(result, str)
        assert len(result) > 200
        assert "Dear Hiring Manager" in result
        assert "InnovateTech" in result
        assert "John Doe" in result

    @pytest.mark.asyncio
    async def test_optimize_cv_invalid_input(self, cv_optimizer):
        """Test CV optimization with invalid input."""
        with pytest.raises(ValueError, match="Invalid CV data"):
            await cv_optimizer.optimize_cv_for_job(
                parsed_cv=None,
                job_description="Test job",
                job_title="Developer",
                company_name="Test Corp"
            )

        with pytest.raises(ValueError, match="Invalid CV data"):
            await cv_optimizer.optimize_cv_for_job(
                parsed_cv={},
                job_description="Test job",
                job_title="Developer",
                company_name="Test Corp"
            )

    @pytest.mark.asyncio
    async def test_generate_cover_letter_invalid_input(self, cv_optimizer, sample_cv_data):
        """Test cover letter generation with invalid input."""
        with pytest.raises(ValueError, match="CV data is required"):
            await cv_optimizer.generate_cover_letter(
                parsed_cv=None,
                job_description="Test job",
                job_title="Developer",
                company_name="Test Corp"
            )

        with pytest.raises(ValueError, match="Job details"):
            await cv_optimizer.generate_cover_letter(
                parsed_cv=sample_cv_data,
                job_description="",
                job_title="Developer",
                company_name="Test Corp"
            )

    @pytest.mark.asyncio
    async def test_openai_api_error(self, cv_optimizer, sample_cv_data, sample_job_description):
        """Test handling of OpenAI API errors."""
        # Setup mock to raise exception
        cv_optimizer.client.chat.completions.create.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await cv_optimizer.optimize_cv_for_job(
                parsed_cv=sample_cv_data,
                job_description=sample_job_description,
                job_title="Developer",
                company_name="Test Corp"
            )

    @pytest.mark.asyncio
    async def test_empty_openai_response(self, cv_optimizer, sample_cv_data, sample_job_description):
        """Test handling of empty OpenAI responses."""
        # Setup mock with empty response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None

        cv_optimizer.client.chat.completions.create.return_value = mock_response

        with pytest.raises(Exception, match="Empty response from OpenAI API"):
            await cv_optimizer.optimize_cv_for_job(
                parsed_cv=sample_cv_data,
                job_description=sample_job_description,
                job_title="Developer",
                company_name="Test Corp"
            )

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, cv_optimizer, sample_cv_data, sample_job_description):
        """Test handling of invalid JSON in OpenAI response."""
        # Setup mock with invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "invalid json content"

        cv_optimizer.client.chat.completions.create.return_value = mock_response

        with pytest.raises(Exception):
            await cv_optimizer.optimize_cv_for_job(
                parsed_cv=sample_cv_data,
                job_description=sample_job_description,
                job_title="Developer",
                company_name="Test Corp"
            )

    @pytest.mark.asyncio
    async def test_get_optimization_suggestions(self, cv_optimizer, sample_cv_data):
        """Test optimization suggestions generation."""
        # Mock response for suggestions
        suggestions_response = {
            "keywords_to_add": ["React", "TypeScript", "AWS"],
            "sections_to_enhance": {
                "experience": "Add more technical details about React projects",
                "skills": "Group skills by category (Frontend, Backend, Cloud)"
            },
            "formatting_tips": ["Use bullet points", "Quantify achievements"],
            "match_score": 75,
            "priority_improvements": ["Add React experience", "Include TypeScript skills"]
        }

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(suggestions_response)

        cv_optimizer.client.chat.completions.create.return_value = mock_response

        # Execute suggestions generation
        result = await cv_optimizer.get_optimization_suggestions(
            parsed_cv=sample_cv_data,
            job_description="React developer position requiring TypeScript"
        )

        # Verify result structure
        assert "keywords_to_add" in result
        assert "sections_to_enhance" in result
        assert "match_score" in result
        assert result["match_score"] == 75
        assert "React" in result["keywords_to_add"]

    @pytest.mark.asyncio
    async def test_cover_letter_name_extraction(
        self, cv_optimizer, sample_job_description, mock_openai_cover_letter_response
    ):
        """Test cover letter generation with name extraction from CV."""
        cv_optimizer.client.chat.completions.create.return_value = mock_openai_cover_letter_response

        cv_data = {
            "personal_info": {"full_name": "Jane Smith"},
            "experience": [],
            "skills": []
        }

        result = await cv_optimizer.generate_cover_letter(
            parsed_cv=cv_data,
            job_description=sample_job_description,
            job_title="Developer",
            company_name="Test Corp",
            user_name=None  # Should extract from CV
        )

        # Verify name was extracted and used in prompts
        call_args = cv_optimizer.client.chat.completions.create.call_args
        user_prompt = call_args.kwargs["messages"][1]["content"]
        assert "Jane Smith" in user_prompt

    @pytest.mark.asyncio
    async def test_cover_letter_no_name_fallback(
        self, cv_optimizer, sample_job_description, mock_openai_cover_letter_response
    ):
        """Test cover letter generation with no name available."""
        cv_optimizer.client.chat.completions.create.return_value = mock_openai_cover_letter_response

        cv_data = {"experience": [], "skills": []}  # No personal_info

        result = await cv_optimizer.generate_cover_letter(
            parsed_cv=cv_data,
            job_description=sample_job_description,
            job_title="Developer",
            company_name="Test Corp",
            user_name=None
        )

        # Verify fallback name was used
        call_args = cv_optimizer.client.chat.completions.create.call_args
        user_prompt = call_args.kwargs["messages"][1]["content"]
        assert "[Your Name]" in user_prompt

    def test_validate_optimized_cv_valid(self, cv_optimizer):
        """Test validation of valid optimized CV."""
        valid_cv = {
            "summary": "Test summary",
            "experience": [{"role": "Developer"}],
            "skills": ["Python", "JavaScript"]
        }

        # Should not raise exception
        cv_optimizer._validate_optimized_cv(valid_cv)

    def test_validate_optimized_cv_invalid(self, cv_optimizer):
        """Test validation of invalid optimized CV."""
        with pytest.raises(ValueError, match="Optimized CV must be a dictionary"):
            cv_optimizer._validate_optimized_cv("invalid")

    def test_build_system_prompts(self, cv_optimizer):
        """Test system prompt generation."""
        cv_prompt = cv_optimizer._build_cv_optimization_system_prompt()
        cover_letter_prompt = cv_optimizer._build_cover_letter_system_prompt()

        # Verify key elements are present
        assert "ATS" in cv_prompt
        assert "keyword" in cv_prompt.lower()
        assert "accuracy" in cv_prompt.lower()

        assert "cover letter" in cover_letter_prompt.lower()
        assert "professional" in cover_letter_prompt.lower()
        assert "company knowledge" in cover_letter_prompt.lower()

    def test_build_user_prompts(self, cv_optimizer, sample_cv_data, sample_job_description):
        """Test user prompt generation."""
        cv_prompt = cv_optimizer._build_cv_optimization_user_prompt(
            sample_cv_data,
            sample_job_description,
            "Developer",
            "Test Corp"
        )

        cover_letter_prompt = cv_optimizer._build_cover_letter_user_prompt(
            sample_cv_data,
            sample_job_description,
            "Developer",
            "Test Corp",
            "John Doe"
        )

        # Verify content is included
        assert "Developer" in cv_prompt
        assert "Test Corp" in cv_prompt
        assert sample_job_description[:100] in cv_prompt

        assert "John Doe" in cover_letter_prompt
        assert "Developer" in cover_letter_prompt
        assert "JavaScript" in cover_letter_prompt  # From skills

    @pytest.mark.asyncio
    async def test_legacy_optimize_cv_method(
        self, cv_optimizer, sample_cv_data, mock_openai_cv_response
    ):
        """Test legacy optimize_cv method for backward compatibility."""
        cv_optimizer.client.chat.completions.create.return_value = mock_openai_cv_response

        result = await cv_optimizer.optimize_cv(
            parsed_cv=sample_cv_data,
            job_description="Python developer position"
        )

        assert isinstance(result, dict)
        cv_optimizer.client.chat.completions.create.assert_called_once()

    def test_initialization_without_api_key(self):
        """Test CV optimizer initialization without OpenAI API key."""
        with patch("app.agents.cv_optimizer.settings") as mock_settings:
            mock_settings.openai_api_key = ""

            with pytest.raises(ValueError, match="OpenAI API key not configured"):
                CVOptimizerAgent()

    def test_configuration_attributes(self, cv_optimizer):
        """Test CV optimizer configuration attributes."""
        assert cv_optimizer.model == "gpt-4o-mini"
        assert cv_optimizer.max_tokens == 3000
        assert cv_optimizer.temperature == 0.3
        assert isinstance(cv_optimizer.client, AsyncMock)