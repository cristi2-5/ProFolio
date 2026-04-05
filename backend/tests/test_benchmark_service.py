"""
Tests for Benchmark Service — GDPR-compliant competitive scoring tests.

Comprehensive test suite covering benchmark calculation, peer group filtering,
skill gap analysis, and privacy compliance validation.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from app.models.user import User
from app.models.benchmark import BenchmarkScore
from app.services.benchmark_service import BenchmarkService, InsufficientPeersError


class TestBenchmarkService:
    """Test benchmark service functionality."""

    @pytest.fixture
    def benchmark_service(self):
        """Create benchmark service instance."""
        return BenchmarkService()

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.full_name = "John Doe"
        user.email = "john@example.com"
        user.seniority_level = "senior"
        user.benchmark_opt_in = True
        return user

    @pytest.fixture
    def sample_job(self):
        """Sample job for testing."""
        job = Mock(spec=ScrapedJob)
        job.id = uuid.uuid4()
        job.job_title = "Senior React Developer"
        job.company_name = "TechCorp"
        job.description = """
        Senior React Developer position requiring 5+ years experience with React,
        TypeScript, JavaScript, Node.js. Experience with AWS, Docker preferred.

        Responsibilities:
        - Develop scalable web applications
        - Collaborate with cross-functional teams
        - Implement best practices for code quality
        """
        return job

    @pytest.fixture
    def sample_user_profile(self):
        """Sample user profile from resume."""
        return {
            "personal_info": {"full_name": "John Doe"},
            "summary": "Senior developer with 6+ years of React experience",
            "experience": [
                {
                    "role": "Senior Frontend Developer",
                    "company": "StartupXYZ",
                    "duration": "2020-2023",
                    "description": "Led React development team"
                },
                {
                    "role": "React Developer",
                    "company": "WebCorp",
                    "duration": "2018-2020",
                    "description": "Built React applications with TypeScript"
                }
            ],
            "skills": ["React", "TypeScript", "JavaScript", "Node.js", "Python"],
            "technologies": ["AWS", "Docker", "Git", "Jest"]
        }

    @pytest.fixture
    def sample_peer_group(self):
        """Sample peer group data."""
        return [
            {
                "user_id": str(uuid.uuid4()),
                "seniority_level": "senior",
                "profile": {
                    "skills": ["React", "JavaScript", "Angular", "Node.js"],
                    "technologies": ["AWS", "Azure"],
                    "experience": [
                        {"role": "Frontend Dev", "company": "Company1"},
                        {"role": "Full Stack Dev", "company": "Company2"}
                    ]
                },
                "anonymized": True
            },
            {
                "user_id": str(uuid.uuid4()),
                "seniority_level": "senior",
                "profile": {
                    "skills": ["React", "TypeScript", "Vue", "Python"],
                    "technologies": ["Docker", "Kubernetes"],
                    "experience": [
                        {"role": "Senior Developer", "company": "Company3"}
                    ]
                },
                "anonymized": True
            },
            # Add 28 more minimal peers to meet minimum threshold
            *[
                {
                    "user_id": str(uuid.uuid4()),
                    "seniority_level": "senior",
                    "profile": {
                        "skills": ["JavaScript", "React"],
                        "technologies": ["AWS"],
                        "experience": [{"role": "Developer", "company": f"Company{i}"}]
                    },
                    "anonymized": True
                }
                for i in range(3, 31)
            ]
        ]

    @pytest.mark.asyncio
    async def test_calculate_benchmark_score_success(
        self, benchmark_service, sample_user, sample_job, sample_user_profile, sample_peer_group
    ):
        """Test successful benchmark score calculation."""
        mock_db = AsyncMock()

        # Mock user job creation/retrieval
        user_job = Mock(spec=UserJob)
        user_job.id = uuid.uuid4()
        user_job.user_id = sample_user.id
        user_job.job_id = sample_job.id

        # Mock profile retrieval
        benchmark_service._get_user_profile = AsyncMock(return_value=sample_user_profile)
        benchmark_service._get_or_create_user_job = AsyncMock(return_value=user_job)
        benchmark_service._get_peer_group = AsyncMock(return_value=sample_peer_group)

        # Mock benchmark score creation
        benchmark_score = Mock(spec=BenchmarkScore)
        benchmark_score.id = uuid.uuid4()
        benchmark_score.score = 75
        benchmark_score.benchmark_data = {
            "peer_group_size": len(sample_peer_group),
            "skill_gaps": [
                {
                    "skill": "docker",
                    "priority": "medium",
                    "peer_frequency": "60%",
                    "recommendation": "Learn containerization"
                }
            ]
        }
        benchmark_score.calculated_at = datetime.now(timezone.utc)

        benchmark_service._create_benchmark_score = AsyncMock(return_value=benchmark_score)

        # Execute calculation
        result = await benchmark_service.calculate_benchmark_score(
            user=sample_user,
            job=sample_job,
            db=mock_db
        )

        # Verify result
        assert result == benchmark_score
        assert result.score == 75

        # Verify method calls
        benchmark_service._get_user_profile.assert_called_once_with(sample_user, mock_db)
        benchmark_service._get_peer_group.assert_called_once_with(sample_user, sample_job, mock_db)

    @pytest.mark.asyncio
    async def test_calculate_benchmark_user_not_opted_in(
        self, benchmark_service, sample_user, sample_job
    ):
        """Test benchmark calculation when user hasn't opted in."""
        sample_user.benchmark_opt_in = False
        mock_db = AsyncMock()

        with pytest.raises(ValueError, match="User has not opted into benchmarking"):
            await benchmark_service.calculate_benchmark_score(
                user=sample_user,
                job=sample_job,
                db=mock_db
            )

    @pytest.mark.asyncio
    async def test_calculate_benchmark_insufficient_peers(
        self, benchmark_service, sample_user, sample_job, sample_user_profile
    ):
        """Test benchmark calculation with insufficient peer data."""
        mock_db = AsyncMock()

        # Mock small peer group (below minimum threshold)
        small_peer_group = [
            {
                "user_id": str(uuid.uuid4()),
                "seniority_level": "senior",
                "profile": {"skills": ["React"], "experience": []},
                "anonymized": True
            }
        ] * 10  # Only 10 peers, below minimum of 30

        benchmark_service._get_user_profile = AsyncMock(return_value=sample_user_profile)
        benchmark_service._get_or_create_user_job = AsyncMock(return_value=Mock())
        benchmark_service._get_peer_group = AsyncMock(return_value=small_peer_group)

        with pytest.raises(InsufficientPeersError, match="10 users found"):
            await benchmark_service.calculate_benchmark_score(
                user=sample_user,
                job=sample_job,
                db=mock_db
            )

    def test_extract_job_requirements(self, benchmark_service, sample_job):
        """Test job requirements extraction."""
        requirements = benchmark_service._extract_job_requirements(sample_job)

        # Verify extracted data
        assert "react" in requirements["required_skills"]
        assert "typescript" in requirements["required_skills"]
        assert "javascript" in requirements["required_skills"]
        assert "node.js" in requirements["required_skills"]
        assert requirements["min_experience_years"] == 5
        assert requirements["job_level"] == "senior"
        assert requirements["job_title"] == "senior react developer"

    def test_calculate_match_score_perfect_match(
        self, benchmark_service, sample_user_profile
    ):
        """Test match score calculation with perfect skill overlap."""
        job_requirements = {
            "required_skills": ["react", "typescript", "javascript"],
            "min_experience_years": 3,
            "job_level": "senior",
            "industry_keywords": [],
            "job_title": "react developer"
        }

        score = benchmark_service._calculate_match_score(
            sample_user_profile, job_requirements, "senior"
        )

        # Should be high score due to skill overlap
        assert score > 70
        assert score <= 100

    def test_calculate_match_score_no_overlap(self, benchmark_service):
        """Test match score with no skill overlap."""
        user_profile = {
            "skills": ["php", "mysql", "wordpress"],
            "technologies": ["apache"],
            "experience": [{"role": "Web Developer", "company": "Agency"}]
        }

        job_requirements = {
            "required_skills": ["react", "typescript", "angular"],
            "min_experience_years": 5,
            "job_level": "senior",
            "industry_keywords": [],
            "job_title": "frontend developer"
        }

        score = benchmark_service._calculate_match_score(
            user_profile, job_requirements, "senior"
        )

        # Should be low score due to no skill overlap
        assert score < 30

    def test_calculate_percentile_rank(self, benchmark_service):
        """Test percentile rank calculation."""
        user_score = 75.0
        peer_scores = [60.0, 65.0, 70.0, 80.0, 85.0, 90.0]

        percentile = benchmark_service._calculate_percentile_rank(user_score, peer_scores)

        # User score 75 is higher than 3 out of 6 peers (50%)
        assert percentile == 51  # 50% + 1 to avoid 0th percentile

    def test_calculate_percentile_rank_highest(self, benchmark_service):
        """Test percentile rank when user has highest score."""
        user_score = 95.0
        peer_scores = [60.0, 70.0, 80.0, 85.0]

        percentile = benchmark_service._calculate_percentile_rank(user_score, peer_scores)

        # User has highest score
        assert percentile == 100

    def test_calculate_percentile_rank_lowest(self, benchmark_service):
        """Test percentile rank when user has lowest score."""
        user_score = 50.0
        peer_scores = [60.0, 70.0, 80.0, 90.0]

        percentile = benchmark_service._calculate_percentile_rank(user_score, peer_scores)

        # User has lowest score but gets minimum rank of 1
        assert percentile == 1

    def test_analyze_skill_gaps(
        self, benchmark_service, sample_user_profile, sample_peer_group
    ):
        """Test skill gap analysis."""
        job_requirements = {
            "required_skills": ["react", "typescript", "docker", "kubernetes", "aws"]
        }

        skill_gaps = benchmark_service._analyze_skill_gaps(
            sample_user_profile, job_requirements, sample_peer_group
        )

        # Should identify missing skills
        assert len(skill_gaps) <= 3  # Top 3 gaps

        # Check structure of gaps
        for gap in skill_gaps:
            assert "skill" in gap
            assert "priority" in gap
            assert "peer_frequency" in gap
            assert "recommendation" in gap
            assert gap["priority"] in ["high", "medium", "low"]

    def test_analyze_skill_gaps_no_missing_skills(
        self, benchmark_service, sample_peer_group
    ):
        """Test skill gap analysis when user has all required skills."""
        user_profile = {
            "skills": ["react", "typescript", "javascript", "docker", "aws"],
            "technologies": ["kubernetes"],
            "experience": []
        }

        job_requirements = {
            "required_skills": ["react", "typescript", "javascript"]
        }

        skill_gaps = benchmark_service._analyze_skill_gaps(
            user_profile, job_requirements, sample_peer_group
        )

        # Should have no gaps
        assert len(skill_gaps) == 0

    def test_score_skill_match_perfect(self, benchmark_service):
        """Test skill matching with perfect overlap."""
        user_skills = ["React", "TypeScript", "JavaScript", "Node.js"]
        required_skills = ["react", "typescript", "javascript"]

        score, max_score = benchmark_service._score_skill_match(user_skills, required_skills)

        # Should get perfect score plus bonus for extra skills
        assert score > 1.0  # Perfect match + bonus
        assert max_score == 1.2

    def test_score_skill_match_partial(self, benchmark_service):
        """Test skill matching with partial overlap."""
        user_skills = ["React", "Vue"]
        required_skills = ["react", "typescript", "angular"]

        score, max_score = benchmark_service._score_skill_match(user_skills, required_skills)

        # Should get partial score (1/3)
        assert score == pytest.approx(1/3, rel=1e-2)

    def test_score_experience_match_sufficient(self, benchmark_service):
        """Test experience matching with sufficient years."""
        user_years = 6
        required_years = 5
        seniority = "senior"

        score, max_score = benchmark_service._score_experience_match(
            user_years, required_years, seniority
        )

        # Should get perfect score
        assert score == 1.0
        assert max_score == 1.0

    def test_score_experience_match_insufficient(self, benchmark_service):
        """Test experience matching with insufficient years."""
        user_years = 2
        required_years = 5
        seniority = "junior"

        score, max_score = benchmark_service._score_experience_match(
            user_years, required_years, seniority
        )

        # Should get reduced score
        assert score < 1.0
        assert score > 0.0

    def test_get_skill_recommendation(self, benchmark_service):
        """Test skill learning recommendations."""
        # Test known skill
        recommendation = benchmark_service._get_skill_recommendation("react")
        assert "React" in recommendation
        assert "documentation" in recommendation.lower()

        # Test unknown skill
        recommendation = benchmark_service._get_skill_recommendation("unknownskill")
        assert "unknownskill" in recommendation
        assert "documentation" in recommendation

    def test_extract_user_skills(self, benchmark_service, sample_user_profile):
        """Test user skills extraction."""
        skills = benchmark_service._extract_user_skills(sample_user_profile)

        # Should combine skills and technologies
        expected_skills = ["React", "TypeScript", "JavaScript", "Node.js", "Python", "AWS", "Docker", "Git", "Jest"]
        assert all(skill in skills for skill in ["React", "TypeScript", "AWS", "Docker"])

    def test_calculate_user_experience(self, benchmark_service, sample_user_profile):
        """Test user experience calculation."""
        years = benchmark_service._calculate_user_experience(sample_user_profile)

        # Should count number of roles (simplified calculation)
        assert years == 2  # Two experience entries

    def test_extract_technology_keywords(self, benchmark_service, sample_job):
        """Test technology keyword extraction for niche filtering."""
        keywords = benchmark_service._extract_technology_keywords(sample_job)

        # Should extract web-related keywords
        assert "web" in keywords

    def test_infer_job_level(self, benchmark_service):
        """Test job level inference."""
        # Senior level
        assert benchmark_service._infer_job_level("Senior Staff Engineer position") == "senior"

        # Junior level
        assert benchmark_service._infer_job_level("Entry level graduate developer") == "junior"

        # Mid level (default)
        assert benchmark_service._infer_job_level("Software Developer position") == "mid"

    def test_infer_company_type(self, benchmark_service):
        """Test company type inference."""
        assert benchmark_service._infer_company_type("TechCorp Inc") == "enterprise"
        assert benchmark_service._infer_company_type("StartupXYZ Labs") == "startup"
        assert benchmark_service._infer_company_type("Generic Company") == "company"

    @pytest.mark.asyncio
    async def test_get_peer_group_filtering(self, benchmark_service, sample_user, sample_job):
        """Test peer group filtering logic."""
        mock_db = AsyncMock()

        # Mock database query results
        mock_peer1 = Mock()
        mock_peer1.id = uuid.uuid4()
        mock_peer1.seniority_level = "senior"
        mock_peer1.benchmark_opt_in = True

        mock_resume1 = Mock()
        mock_resume1.parsed_data = {"skills": ["React", "JavaScript"]}

        mock_db.execute.return_value.all.return_value = [(mock_peer1, mock_resume1)]

        peer_group = await benchmark_service._get_peer_group(sample_user, sample_job, mock_db)

        # Verify peer group structure
        assert len(peer_group) == 1
        assert peer_group[0]["seniority_level"] == "senior"
        assert peer_group[0]["anonymized"] is True
        assert "user_id" in peer_group[0]  # For deduplication only

    @pytest.mark.asyncio
    async def test_error_handling_with_rollback(
        self, benchmark_service, sample_user, sample_job, sample_user_profile
    ):
        """Test error handling with database rollback."""
        mock_db = AsyncMock()

        # Mock exception during calculation
        benchmark_service._get_user_profile = AsyncMock(return_value=sample_user_profile)
        benchmark_service._get_or_create_user_job = AsyncMock(return_value=Mock())
        benchmark_service._get_peer_group = AsyncMock(side_effect=Exception("Database error"))

        with pytest.raises(Exception, match="Database error"):
            await benchmark_service.calculate_benchmark_score(
                user=sample_user,
                job=sample_job,
                db=mock_db
            )

        # Verify rollback was called
        mock_db.rollback.assert_called_once()

    def test_minimum_peer_count_constant(self, benchmark_service):
        """Test minimum peer count requirement."""
        assert benchmark_service.MINIMUM_PEER_COUNT == 30

    def test_skill_match_weights_configuration(self, benchmark_service):
        """Test skill matching weights configuration."""
        weights = benchmark_service.SKILL_MATCH_WEIGHTS

        assert "exact_match" in weights
        assert "partial_match" in weights
        assert weights["exact_match"] == 1.0
        assert weights["partial_match"] < weights["exact_match"]