"""
Tests for Interview Coach Agent — AI-powered interview preparation.

Comprehensive test suite covering interview question generation, company research,
cheat sheet creation, and preparation strategy development.
"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
from openai import AsyncOpenAI

from app.agents.interview_coach import InterviewCoachAgent


class TestInterviewCoachAgent:
    """Test interview coach agent functionality."""

    @pytest.fixture
    def interview_coach(self):
        """Create interview coach agent with mocked OpenAI client."""
        with patch("app.agents.interview_coach.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            agent = InterviewCoachAgent()
            agent.client = AsyncMock(spec=AsyncOpenAI)
            return agent

    @pytest.fixture
    def sample_job_description(self):
        """Sample job description for testing."""
        return """
        Senior Full Stack Developer - TechCorp

        We are looking for an experienced Full Stack Developer to join our team.

        Requirements:
        - 5+ years experience with React and Node.js
        - Proficiency in TypeScript and JavaScript
        - Experience with AWS cloud services and Docker
        - Knowledge of microservices architecture
        - Strong problem-solving and communication skills

        Responsibilities:
        - Design and develop scalable web applications
        - Collaborate with cross-functional teams
        - Implement best practices for code quality
        - Mentor junior developers
        """

    @pytest.fixture
    def sample_user_background(self):
        """Sample user background from CV."""
        return {
            "personal_info": {"full_name": "John Doe"},
            "summary": "Senior developer with 6 years of experience",
            "experience": [
                {
                    "role": "Senior Developer",
                    "company": "StartupXYZ",
                    "description": "Led development of React applications"
                }
            ],
            "skills": ["React", "Node.js", "TypeScript", "AWS", "Docker"]
        }

    @pytest.fixture
    def mock_openai_technical_response(self):
        """Mock OpenAI response for technical questions."""
        technical_questions = [
            {
                "question": "How would you optimize a React application's performance?",
                "difficulty": "intermediate",
                "topics": ["React", "Performance", "Optimization"],
                "guidance": "Discuss memo, useMemo, useCallback, code splitting",
                "sample_answer": "I would start by profiling..."
            },
            {
                "question": "Explain the event loop in Node.js.",
                "difficulty": "advanced",
                "topics": ["Node.js", "JavaScript", "Asynchronous"],
                "guidance": "Cover call stack, event loop phases, libuv",
                "sample_answer": "The Node.js event loop..."
            }
        ]

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(technical_questions)
        return mock_response

    @pytest.fixture
    def mock_openai_behavioral_response(self):
        """Mock OpenAI response for behavioral questions."""
        behavioral_questions = [
            {
                "question": "Tell me about a time you had to work with a difficult team member.",
                "scenario": "Assessing collaboration and conflict resolution skills",
                "star_guidance": "Situation: Describe the conflict. Task: What needed to be done. Action: How you handled it. Result: Positive outcome.",
                "company_context": "TechCorp values teamwork and collaboration"
            },
            {
                "question": "Describe a challenging technical problem you solved.",
                "scenario": "Evaluating problem-solving methodology",
                "star_guidance": "Focus on your systematic approach to debugging and solution implementation",
                "company_context": "TechCorp emphasizes innovative problem-solving"
            }
        ]

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(behavioral_questions)
        return mock_response

    @pytest.fixture
    def mock_openai_company_response(self):
        """Mock OpenAI response for company research."""
        company_research = [
            {
                "topic": "Company Culture",
                "information": "TechCorp emphasizes innovation and employee growth",
                "talking_points": ["Commitment to learning", "Innovation mindset"],
                "questions_to_ask": ["What learning opportunities are available?"]
            },
            {
                "topic": "Recent Developments",
                "information": "Recently launched new AI product line",
                "talking_points": ["AI expertise", "Product innovation"],
                "questions_to_ask": ["How is the AI product line performing?"]
            }
        ]

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(company_research)
        return mock_response

    @pytest.fixture
    def mock_openai_cheat_sheet_response(self):
        """Mock OpenAI response for technology cheat sheet."""
        cheat_sheet = [
            {
                "concept": "React Hooks",
                "definition": "Functions that let you use state and lifecycle in functional components",
                "key_points": ["useState for state", "useEffect for side effects"],
                "practical_example": "const [count, setCount] = useState(0);"
            },
            {
                "concept": "Microservices",
                "definition": "Architectural approach with small, independent services",
                "key_points": ["Scalability", "Fault isolation", "Technology diversity"],
                "practical_example": "User service, Payment service, Inventory service"
            }
        ]

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(cheat_sheet)
        return mock_response

    @pytest.fixture
    def mock_openai_strategy_response(self):
        """Mock OpenAI response for preparation strategy."""
        strategy = {
            "timeline": "2-3 weeks of preparation recommended",
            "focus_areas": ["React performance optimization", "Node.js fundamentals"],
            "practice_recommendations": ["Code challenges", "System design practice"],
            "confidence_boosters": ["Review past projects", "Practice explanations"],
            "day_of_tips": ["Arrive early", "Prepare questions", "Stay calm"]
        }

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(strategy)
        return mock_response

    @pytest.mark.asyncio
    async def test_generate_interview_prep_materials_success(
        self,
        interview_coach,
        sample_job_description,
        sample_user_background,
        mock_openai_technical_response,
        mock_openai_behavioral_response,
        mock_openai_company_response,
        mock_openai_cheat_sheet_response,
        mock_openai_strategy_response
    ):
        """Test successful complete interview prep generation."""
        # Setup mocks for all API calls
        interview_coach.client.chat.completions.create.side_effect = [
            mock_openai_technical_response,
            mock_openai_behavioral_response,
            mock_openai_company_response,
            mock_openai_cheat_sheet_response,
            mock_openai_strategy_response
        ]

        # Execute generation
        result = await interview_coach.generate_interview_prep_materials(
            job_description=sample_job_description,
            job_title="Senior Full Stack Developer",
            company_name="TechCorp",
            user_experience_level="senior",
            user_background=sample_user_background
        )

        # Verify API was called 5 times
        assert interview_coach.client.chat.completions.create.call_count == 5

        # Verify result structure
        assert isinstance(result, dict)
        assert "technical_questions" in result
        assert "behavioral_questions" in result
        assert "company_research" in result
        assert "technology_cheat_sheet" in result
        assert "preparation_strategy" in result

        # Verify content
        assert len(result["technical_questions"]) == 2
        assert result["technical_questions"][0]["question"] == "How would you optimize a React application's performance?"
        assert len(result["behavioral_questions"]) == 2
        assert result["behavioral_questions"][0]["scenario"] == "Assessing collaboration and conflict resolution skills"

    @pytest.mark.asyncio
    async def test_generate_technical_questions_success(
        self, interview_coach, sample_job_description, mock_openai_technical_response
    ):
        """Test successful technical question generation."""
        interview_coach.client.chat.completions.create.return_value = mock_openai_technical_response

        result = await interview_coach.generate_technical_questions(
            job_description=sample_job_description,
            job_title="Senior Full Stack Developer",
            user_experience_level="senior",
            question_count=3
        )

        # Verify API call
        interview_coach.client.chat.completions.create.assert_called_once()
        call_args = interview_coach.client.chat.completions.create.call_args

        assert call_args.kwargs["model"] == "gpt-4o-mini"
        assert call_args.kwargs["response_format"] == {"type": "json_object"}
        assert len(call_args.kwargs["messages"]) == 2

        # Verify result
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["difficulty"] == "intermediate"
        assert "React" in result[0]["topics"]

    @pytest.mark.asyncio
    async def test_generate_behavioral_questions_success(
        self, interview_coach, sample_job_description, mock_openai_behavioral_response
    ):
        """Test successful behavioral question generation."""
        interview_coach.client.chat.completions.create.return_value = mock_openai_behavioral_response

        result = await interview_coach.generate_behavioral_questions(
            job_description=sample_job_description,
            company_name="TechCorp",
            job_title="Senior Full Stack Developer",
            question_count=2
        )

        # Verify result structure
        assert isinstance(result, list)
        assert len(result) == 2
        assert "star_guidance" in result[0]
        assert "company_context" in result[0]
        assert "TechCorp" in result[0]["company_context"]

    @pytest.mark.asyncio
    async def test_generate_company_research_success(
        self, interview_coach, sample_job_description, mock_openai_company_response
    ):
        """Test successful company research generation."""
        interview_coach.client.chat.completions.create.return_value = mock_openai_company_response

        result = await interview_coach.generate_company_research(
            company_name="TechCorp",
            job_title="Senior Full Stack Developer",
            job_description=sample_job_description
        )

        # Verify result structure
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["topic"] == "Company Culture"
        assert "talking_points" in result[0]
        assert "questions_to_ask" in result[0]

    @pytest.mark.asyncio
    async def test_generate_technology_cheatsheet_success(
        self, interview_coach, sample_job_description, mock_openai_cheat_sheet_response
    ):
        """Test successful technology cheat sheet generation."""
        interview_coach.client.chat.completions.create.return_value = mock_openai_cheat_sheet_response

        result = await interview_coach.generate_technology_cheatsheet(
            job_description=sample_job_description,
            job_title="Senior Full Stack Developer"
        )

        # Verify result structure
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["concept"] == "React Hooks"
        assert "key_points" in result[0]
        assert "practical_example" in result[0]

    @pytest.mark.asyncio
    async def test_generate_preparation_strategy_success(
        self, interview_coach, sample_job_description, mock_openai_strategy_response
    ):
        """Test successful preparation strategy generation."""
        interview_coach.client.chat.completions.create.return_value = mock_openai_strategy_response

        result = await interview_coach.generate_preparation_strategy(
            job_description=sample_job_description,
            job_title="Senior Full Stack Developer",
            user_experience_level="senior"
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "timeline" in result
        assert "focus_areas" in result
        assert "practice_recommendations" in result
        assert result["timeline"] == "2-3 weeks of preparation recommended"

    @pytest.mark.asyncio
    async def test_generate_prep_without_user_background(
        self, interview_coach, sample_job_description, mock_openai_technical_response
    ):
        """Test interview prep generation without user background."""
        interview_coach.client.chat.completions.create.return_value = mock_openai_technical_response

        result = await interview_coach.generate_interview_prep_materials(
            job_description=sample_job_description,
            job_title="Developer",
            company_name="TechCorp"
        )

        # Should still generate materials
        assert isinstance(result, dict)
        assert "technical_questions" in result

    @pytest.mark.asyncio
    async def test_invalid_input_validation(self, interview_coach):
        """Test validation of invalid inputs."""
        with pytest.raises(ValueError, match="Job description is required"):
            await interview_coach.generate_interview_prep_materials(
                job_description="",
                job_title="Developer",
                company_name="TechCorp"
            )

        with pytest.raises(ValueError, match="Job title is required"):
            await interview_coach.generate_technical_questions(
                job_description="Valid description",
                job_title="",
                user_experience_level="junior"
            )

    @pytest.mark.asyncio
    async def test_openai_api_error_handling(self, interview_coach, sample_job_description):
        """Test handling of OpenAI API errors."""
        interview_coach.client.chat.completions.create.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await interview_coach.generate_technical_questions(
                job_description=sample_job_description,
                job_title="Developer",
                user_experience_level="junior"
            )

    @pytest.mark.asyncio
    async def test_empty_openai_response(self, interview_coach, sample_job_description):
        """Test handling of empty OpenAI responses."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None

        interview_coach.client.chat.completions.create.return_value = mock_response

        with pytest.raises(Exception, match="Empty response from OpenAI API"):
            await interview_coach.generate_technical_questions(
                job_description=sample_job_description,
                job_title="Developer",
                user_experience_level="junior"
            )

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, interview_coach, sample_job_description):
        """Test handling of invalid JSON in OpenAI response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "invalid json content"

        interview_coach.client.chat.completions.create.return_value = mock_response

        with pytest.raises(Exception):
            await interview_coach.generate_technical_questions(
                job_description=sample_job_description,
                job_title="Developer",
                user_experience_level="junior"
            )

    def test_question_count_validation(self, interview_coach):
        """Test validation of question counts."""
        # Valid counts should not raise errors
        interview_coach._validate_question_count(5)
        interview_coach._validate_question_count(1)
        interview_coach._validate_question_count(20)

        # Invalid counts should raise errors
        with pytest.raises(ValueError, match="Question count must be between 1 and 20"):
            interview_coach._validate_question_count(0)

        with pytest.raises(ValueError, match="Question count must be between 1 and 20"):
            interview_coach._validate_question_count(25)

    def test_input_validation_methods(self, interview_coach):
        """Test input validation helper methods."""
        # Valid inputs should not raise errors
        interview_coach._validate_job_inputs(
            "Valid job description",
            "Developer",
            "TechCorp"
        )

        # Invalid inputs should raise errors
        with pytest.raises(ValueError, match="Job description is required"):
            interview_coach._validate_job_inputs("", "Developer", "TechCorp")

        with pytest.raises(ValueError, match="Job title is required"):
            interview_coach._validate_job_inputs("Valid", "", "TechCorp")

        with pytest.raises(ValueError, match="Company name is required"):
            interview_coach._validate_job_inputs("Valid", "Developer", "")

    def test_prompt_building_methods(self, interview_coach):
        """Test prompt building methods."""
        # Technical questions prompt
        prompt = interview_coach._build_technical_questions_prompt(
            "Senior Developer job",
            "Senior Developer",
            "senior",
            5
        )
        assert "Senior Developer" in prompt
        assert "senior" in prompt
        assert "5" in prompt

        # Behavioral questions prompt
        prompt = interview_coach._build_behavioral_questions_prompt(
            "Job description",
            "TechCorp",
            "Developer",
            3
        )
        assert "TechCorp" in prompt
        assert "Developer" in prompt

    def test_initialization_without_api_key(self):
        """Test interview coach initialization without OpenAI API key."""
        with patch("app.agents.interview_coach.settings") as mock_settings:
            mock_settings.openai_api_key = ""

            with pytest.raises(ValueError, match="OpenAI API key not configured"):
                InterviewCoachAgent()

    def test_configuration_attributes(self, interview_coach):
        """Test interview coach configuration attributes."""
        assert interview_coach.model == "gpt-4o-mini"
        assert interview_coach.max_tokens == 3000
        assert interview_coach.temperature == 0.4
        assert isinstance(interview_coach.client, AsyncMock)

    @pytest.mark.asyncio
    async def test_experience_level_adaptation(
        self, interview_coach, sample_job_description, mock_openai_technical_response
    ):
        """Test adaptation of questions based on experience level."""
        interview_coach.client.chat.completions.create.return_value = mock_openai_technical_response

        # Test junior level
        result_junior = await interview_coach.generate_technical_questions(
            job_description=sample_job_description,
            job_title="Developer",
            user_experience_level="junior",
            question_count=2
        )

        # Test senior level
        result_senior = await interview_coach.generate_technical_questions(
            job_description=sample_job_description,
            job_title="Developer",
            user_experience_level="senior",
            question_count=2
        )

        # Both should generate questions
        assert isinstance(result_junior, list)
        assert isinstance(result_senior, list)

        # Check that experience level was included in prompts
        call_args = interview_coach.client.chat.completions.create.call_args_list
        junior_prompt = call_args[0].kwargs["messages"][1]["content"]
        senior_prompt = call_args[1].kwargs["messages"][1]["content"]

        assert "junior" in junior_prompt.lower()
        assert "senior" in senior_prompt.lower()

    @pytest.mark.asyncio
    async def test_user_background_integration(
        self, interview_coach, sample_job_description, sample_user_background, mock_openai_technical_response
    ):
        """Test integration of user background in question generation."""
        interview_coach.client.chat.completions.create.return_value = mock_openai_technical_response

        result = await interview_coach.generate_interview_prep_materials(
            job_description=sample_job_description,
            job_title="Developer",
            company_name="TechCorp",
            user_background=sample_user_background
        )

        # Check that user skills were included in the prompt
        call_args = interview_coach.client.chat.completions.create.call_args
        prompt_content = call_args.kwargs["messages"][1]["content"]

        assert "React" in prompt_content
        assert "Node.js" in prompt_content
        assert "StartupXYZ" in prompt_content