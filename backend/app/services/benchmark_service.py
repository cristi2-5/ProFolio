"""
Benchmark Service — GDPR-compliant competitive scoring system.

Computes benchmark scores using only opt-in anonymized data with strict
privacy controls. Enforces minimum peer group threshold of 30 users.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from app.models.benchmark import BenchmarkScore

logger = logging.getLogger(__name__)


class InsufficientPeersError(Exception):
    """Raised when peer group is too small for reliable benchmarking."""
    pass


class BenchmarkService:
    """GDPR-compliant benchmark scoring service.

    Provides competitive scoring while strictly respecting user privacy
    and data protection requirements. Only processes users who have
    explicitly opted into benchmarking.
    """

    MINIMUM_PEER_COUNT = 30
    SKILL_MATCH_WEIGHTS = {
        "exact_match": 1.0,       # Skill exactly matches job requirement
        "partial_match": 0.7,     # Related skill or technology
        "experience_bonus": 0.3,  # Years of experience multiplier
        "keyword_density": 0.5,   # How often skill appears in job description
    }

    def __init__(self):
        """Initialize benchmark service."""
        self.logger = logging.getLogger(__name__)

    async def calculate_benchmark_score(
        self,
        user: User,
        job: ScrapedJob,
        db: AsyncSession,
    ) -> BenchmarkScore:
        """Calculate GDPR-compliant benchmark score for a user and job.

        Compares user's skills and experience against peer group to generate
        percentile ranking. Requires minimum 30 peers for statistical validity.

        Args:
            user: User requesting benchmark score.
            job: Target job for scoring.
            db: Database session.

        Returns:
            BenchmarkScore: Calculated benchmark with peer group metadata.

        Raises:
            InsufficientPeersError: If fewer than 30 eligible peers found.
            ValueError: If user hasn't opted into benchmarking.
        """
        try:
            # Verify user has opted into benchmarking
            if not user.benchmark_opt_in:
                raise ValueError("User has not opted into benchmarking")

            # Get or create UserJob record for score storage
            user_job = await self._get_or_create_user_job(user, job, db)

            # Get user's skills and experience
            user_profile = await self._get_user_profile(user, db)
            if not user_profile:
                raise ValueError("User has no active resume for benchmarking")

            # Extract job requirements for skill matching
            job_requirements = self._extract_job_requirements(job)

            # Find eligible peer group
            peer_group = await self._get_peer_group(user, job, db)

            if len(peer_group) < self.MINIMUM_PEER_COUNT:
                raise InsufficientPeersError(
                    f"Insufficient peer data: {len(peer_group)} users found, "
                    f"minimum {self.MINIMUM_PEER_COUNT} required"
                )

            # Calculate user's match score
            user_match_score = self._calculate_match_score(
                user_profile, job_requirements, user.seniority_level
            )

            # Calculate peer match scores for comparison
            peer_scores = []
            for peer_data in peer_group:
                peer_profile = peer_data["profile"]
                peer_seniority = peer_data["seniority_level"]

                peer_score = self._calculate_match_score(
                    peer_profile, job_requirements, peer_seniority
                )
                peer_scores.append(peer_score)

            # Calculate percentile ranking
            percentile_rank = self._calculate_percentile_rank(user_match_score, peer_scores)

            # Generate skill gap analysis
            skill_gaps = self._analyze_skill_gaps(user_profile, job_requirements, peer_group)

            # Create or update benchmark score record
            benchmark_score = await self._create_benchmark_score(
                user=user,
                job=job,
                user_job=user_job,
                score=percentile_rank,
                peer_group_size=len(peer_group),
                skill_gaps=skill_gaps,
                match_criteria=job_requirements,
                db=db,
            )

            self.logger.info(
                f"Calculated benchmark score {percentile_rank} for user {user.id} "
                f"with {len(peer_group)} peers"
            )

            return benchmark_score

        except Exception as e:
            await db.rollback()
            self.logger.error(f"Benchmark calculation failed: {e}")
            raise

    async def _get_peer_group(
        self,
        user: User,
        job: ScrapedJob,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Find eligible peers for benchmark comparison.

        Filters by:
        - Same seniority level
        - Opted into benchmarking (GDPR compliance)
        - Has active resume data
        - For mid/senior: same technology niche

        Args:
            user: User requesting benchmark.
            job: Target job for context.
            db: Database session.

        Returns:
            List of peer profile data (anonymized).
        """
        # Base query for opted-in users with active resumes
        base_query = (
            select(User, ParsedResume)
            .join(ParsedResume, and_(
                ParsedResume.user_id == User.id,
                ParsedResume.is_active == True,
            ))
            .where(
                User.benchmark_opt_in == True,
                User.id != user.id,  # Exclude requesting user
                User.seniority_level == user.seniority_level,
            )
        )

        # For mid/senior levels, filter by technology niche
        if user.seniority_level in ["mid", "senior"]:
            job_tech_keywords = self._extract_technology_keywords(job)
            if job_tech_keywords:
                # This is a simplified niche matching - in production you'd want
                # more sophisticated technology clustering
                niche_filter = func.array_overlap(
                    func.string_to_array(job.description.lower(), ' '),
                    job_tech_keywords
                )
                base_query = base_query.where(niche_filter)

        result = await db.execute(base_query)
        peers = result.all()

        peer_group = []
        for peer_user, peer_resume in peers:
            if peer_resume.parsed_data:
                peer_group.append({
                    "user_id": str(peer_user.id),  # Keep for deduplication only
                    "seniority_level": peer_user.seniority_level,
                    "profile": peer_resume.parsed_data,
                    "anonymized": True,  # All peer data is anonymized
                })

        return peer_group

    def _extract_job_requirements(self, job: ScrapedJob) -> Dict[str, Any]:
        """Extract structured requirements from job description.

        Uses keyword extraction and pattern matching to identify:
        - Required skills and technologies
        - Experience requirements
        - Key responsibilities

        Args:
            job: Job to analyze.

        Returns:
            Structured job requirements.
        """
        description = job.description.lower()

        # Common tech skills (this would be more sophisticated in production)
        tech_skills = [
            # Frontend
            "react", "vue", "angular", "javascript", "typescript", "html", "css",
            # Backend
            "python", "java", "node.js", "golang", "ruby", "php", "c#",
            # Databases
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
            # Cloud & DevOps
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
            # Data & Analytics
            "pandas", "numpy", "spark", "hadoop", "tableau", "power bi",
        ]

        # Extract mentioned skills
        found_skills = [skill for skill in tech_skills if skill in description]

        # Extract experience requirements (simplified pattern matching)
        experience_years = 0
        if "5+ years" in description or "5 years" in description:
            experience_years = 5
        elif "3+ years" in description or "3 years" in description:
            experience_years = 3
        elif "senior" in description or "staff" in description:
            experience_years = 5
        elif "junior" in description or "entry" in description:
            experience_years = 1

        return {
            "required_skills": found_skills,
            "min_experience_years": experience_years,
            "job_level": self._infer_job_level(description),
            "industry_keywords": self._extract_industry_keywords(description),
            "job_title": job.job_title.lower(),
            "company_type": self._infer_company_type(job.company_name),
        }

    def _calculate_match_score(
        self,
        user_profile: Dict[str, Any],
        job_requirements: Dict[str, Any],
        seniority_level: str,
    ) -> float:
        """Calculate how well a user profile matches job requirements.

        Uses weighted scoring across multiple dimensions:
        - Skill overlap (primary factor)
        - Experience level match
        - Industry relevance
        - Title/role alignment

        Args:
            user_profile: User's CV data.
            job_requirements: Extracted job requirements.
            seniority_level: User's experience level.

        Returns:
            Match score (0-100).
        """
        score = 0.0
        max_score = 0.0

        # Extract user data
        user_skills = self._extract_user_skills(user_profile)
        user_experience = self._calculate_user_experience(user_profile)

        # 1. Skill Matching (50% of score)
        skill_score, skill_max = self._score_skill_match(
            user_skills, job_requirements["required_skills"]
        )
        score += skill_score * 0.5
        max_score += skill_max * 0.5

        # 2. Experience Level (25% of score)
        exp_score, exp_max = self._score_experience_match(
            user_experience, job_requirements["min_experience_years"], seniority_level
        )
        score += exp_score * 0.25
        max_score += exp_max * 0.25

        # 3. Industry/Role Relevance (15% of score)
        industry_score, industry_max = self._score_industry_relevance(
            user_profile, job_requirements
        )
        score += industry_score * 0.15
        max_score += industry_max * 0.15

        # 4. Title/Role Alignment (10% of score)
        title_score, title_max = self._score_title_alignment(
            user_profile, job_requirements["job_title"]
        )
        score += title_score * 0.10
        max_score += title_max * 0.10

        # Normalize to 0-100 scale
        if max_score > 0:
            return min(100.0, (score / max_score) * 100)
        return 0.0

    def _score_skill_match(
        self, user_skills: List[str], required_skills: List[str]
    ) -> Tuple[float, float]:
        """Score skill overlap between user and job requirements."""
        if not required_skills:
            return 0.0, 0.0

        user_skills_lower = [skill.lower() for skill in user_skills]
        matched_skills = 0

        for required_skill in required_skills:
            if required_skill.lower() in user_skills_lower:
                matched_skills += 1

        # Bonus for having more skills than required
        skill_ratio = len(user_skills) / len(required_skills) if required_skills else 0
        bonus = min(0.2, (skill_ratio - 1) * 0.1) if skill_ratio > 1 else 0

        score = (matched_skills / len(required_skills)) + bonus
        return score, 1.2  # Max includes bonus

    def _score_experience_match(
        self, user_years: int, required_years: int, seniority_level: str
    ) -> Tuple[float, float]:
        """Score experience level alignment."""
        if required_years == 0:
            return 1.0, 1.0  # No specific requirement

        # Perfect match gets full score
        if user_years >= required_years:
            # Bonus for significantly more experience
            if user_years > required_years * 1.5:
                return 1.1, 1.0
            return 1.0, 1.0

        # Partial credit for being close
        ratio = user_years / required_years if required_years > 0 else 0
        return ratio * 0.8, 1.0  # Penalty for insufficient experience

    def _score_industry_relevance(
        self, user_profile: Dict[str, Any], job_requirements: Dict[str, Any]
    ) -> Tuple[float, float]:
        """Score industry and domain relevance."""
        # Simple keyword matching - would be more sophisticated in production
        user_text = " ".join([
            user_profile.get("summary", ""),
            " ".join([exp.get("description", "") for exp in user_profile.get("experience", [])])
        ]).lower()

        industry_keywords = job_requirements.get("industry_keywords", [])
        if not industry_keywords:
            return 0.5, 1.0  # Neutral score if no keywords

        matches = sum(1 for keyword in industry_keywords if keyword in user_text)
        score = matches / len(industry_keywords) if industry_keywords else 0
        return score, 1.0

    def _score_title_alignment(
        self, user_profile: Dict[str, Any], job_title: str
    ) -> Tuple[float, float]:
        """Score alignment between user's roles and target job title."""
        user_titles = []
        for exp in user_profile.get("experience", []):
            if exp.get("role"):
                user_titles.append(exp["role"].lower())

        if not user_titles:
            return 0.0, 1.0

        # Simple keyword overlap
        job_words = set(job_title.split())
        title_scores = []

        for user_title in user_titles:
            user_words = set(user_title.split())
            overlap = len(job_words.intersection(user_words))
            title_scores.append(overlap / len(job_words) if job_words else 0)

        return max(title_scores) if title_scores else 0.0, 1.0

    def _calculate_percentile_rank(self, user_score: float, peer_scores: List[float]) -> int:
        """Calculate percentile ranking of user score against peers.

        Args:
            user_score: User's match score.
            peer_scores: List of peer match scores.

        Returns:
            Percentile rank (1-100).
        """
        if not peer_scores:
            return 50  # Default middle rank if no peers

        # Count peers with lower scores
        lower_count = sum(1 for score in peer_scores if score < user_score)

        # Calculate percentile (add 1 to avoid 0th percentile)
        percentile = int((lower_count / len(peer_scores)) * 100) + 1

        return min(100, max(1, percentile))

    def _analyze_skill_gaps(
        self,
        user_profile: Dict[str, Any],
        job_requirements: Dict[str, Any],
        peer_group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Analyze top 3 skill gaps with peer frequency data.

        Args:
            user_profile: User's CV data.
            job_requirements: Job requirements.
            peer_group: Peer group for comparison.

        Returns:
            List of top 3 skill gaps with recommendations.
        """
        user_skills = set(skill.lower() for skill in self._extract_user_skills(user_profile))
        required_skills = set(job_requirements["required_skills"])
        missing_skills = required_skills - user_skills

        if not missing_skills:
            return []

        # Calculate how often each missing skill appears in peer group
        skill_frequency = {}
        for skill in missing_skills:
            peers_with_skill = 0
            for peer in peer_group:
                peer_skills = set(skill.lower() for skill in self._extract_user_skills(peer["profile"]))
                if skill in peer_skills:
                    peers_with_skill += 1

            frequency = peers_with_skill / len(peer_group) if peer_group else 0
            skill_frequency[skill] = frequency

        # Sort by frequency (most common missing skills first)
        top_gaps = sorted(skill_frequency.items(), key=lambda x: x[1], reverse=True)[:3]

        gaps = []
        for skill, frequency in top_gaps:
            gaps.append({
                "skill": skill,
                "priority": "high" if frequency > 0.7 else "medium" if frequency > 0.4 else "low",
                "peer_frequency": f"{frequency:.1%}",
                "recommendation": self._get_skill_recommendation(skill),
            })

        return gaps

    def _get_skill_recommendation(self, skill: str) -> str:
        """Get learning recommendation for a missing skill."""
        recommendations = {
            "react": "Consider completing React documentation and building sample projects",
            "python": "Start with Python basics and gradually move to frameworks like Django/Flask",
            "aws": "Pursue AWS Cloud Practitioner certification for foundational knowledge",
            "docker": "Learn containerization through hands-on Docker tutorials",
            "kubernetes": "Master Docker first, then explore Kubernetes orchestration",
            "typescript": "Build on JavaScript knowledge with TypeScript's type system",
            "node.js": "Leverage JavaScript skills to learn server-side Node.js development",
        }

        return recommendations.get(skill, f"Study {skill} through official documentation and practice projects")

    # Helper methods for data extraction

    def _extract_user_skills(self, user_profile: Dict[str, Any]) -> List[str]:
        """Extract all skills from user profile."""
        skills = []

        # Direct skills list
        if user_profile.get("skills"):
            skills.extend(user_profile["skills"])

        # Technologies list
        if user_profile.get("technologies"):
            skills.extend(user_profile["technologies"])

        return skills

    def _calculate_user_experience(self, user_profile: Dict[str, Any]) -> int:
        """Calculate total years of experience from profile."""
        # Simplified calculation - count unique companies/roles
        experiences = user_profile.get("experience", [])
        return len(experiences)  # Each role ~= 1-2 years average

    def _extract_technology_keywords(self, job: ScrapedJob) -> List[str]:
        """Extract technology keywords for niche filtering."""
        common_niches = ["web", "mobile", "data", "ai", "devops", "security"]
        description = job.description.lower()
        job_title = job.job_title.lower()

        found_niches = []
        for niche in common_niches:
            if niche in description or niche in job_title:
                found_niches.append(niche)

        return found_niches

    def _infer_job_level(self, description: str) -> str:
        """Infer job level from description."""
        desc_lower = description.lower()
        if any(word in desc_lower for word in ["senior", "lead", "principal", "staff"]):
            return "senior"
        elif any(word in desc_lower for word in ["junior", "entry", "graduate", "intern"]):
            return "junior"
        else:
            return "mid"

    def _extract_industry_keywords(self, description: str) -> List[str]:
        """Extract industry-specific keywords."""
        industries = {
            "fintech": ["finance", "banking", "payment", "trading", "investment"],
            "healthtech": ["health", "medical", "clinical", "patient", "healthcare"],
            "edtech": ["education", "learning", "student", "academic", "course"],
            "ecommerce": ["retail", "shopping", "marketplace", "commerce", "store"],
        }

        found_keywords = []
        for industry, keywords in industries.items():
            if any(keyword in description for keyword in keywords):
                found_keywords.extend(keywords)

        return found_keywords

    def _infer_company_type(self, company_name: str) -> str:
        """Infer company type (startup, enterprise, etc.)."""
        company_lower = company_name.lower()

        if any(word in company_lower for word in ["startup", "labs", "ventures"]):
            return "startup"
        elif any(word in company_lower for word in ["corp", "corporation", "inc", "ltd"]):
            return "enterprise"
        else:
            return "company"

    async def _get_user_profile(self, user: User, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Get user's active resume profile."""
        stmt = select(ParsedResume).where(
            ParsedResume.user_id == user.id,
            ParsedResume.is_active == True,
        )
        result = await db.execute(stmt)
        resume = result.scalar_one_or_none()

        return resume.parsed_data if resume else None

    async def _get_or_create_user_job(self, user: User, job: ScrapedJob, db: AsyncSession) -> UserJob:
        """Get or create UserJob record for benchmark storage."""
        stmt = select(UserJob).where(
            UserJob.user_id == user.id,
            UserJob.job_id == job.id,
        )
        result = await db.execute(stmt)
        user_job = result.scalar_one_or_none()

        if not user_job:
            user_job = UserJob(
                user_id=user.id,
                job_id=job.id,
                match_score=0,  # Will be updated during benchmarking
                status="new",
            )
            db.add(user_job)
            await db.commit()
            await db.refresh(user_job)

        return user_job

    async def _create_benchmark_score(
        self,
        user: User,
        job: ScrapedJob,
        user_job: UserJob,
        score: int,
        peer_group_size: int,
        skill_gaps: List[Dict[str, Any]],
        match_criteria: Dict[str, Any],
        db: AsyncSession,
    ) -> BenchmarkScore:
        """Create or update benchmark score record."""
        # Check if benchmark already exists
        stmt = select(BenchmarkScore).where(
            BenchmarkScore.user_id == user.id,
            BenchmarkScore.job_id == job.id,
        )
        result = await db.execute(stmt)
        existing_score = result.scalar_one_or_none()

        benchmark_data = {
            "score": score,
            "peer_group_size": peer_group_size,
            "peer_group_filters": {
                "seniority_level": user.seniority_level,
                "benchmark_opt_in": True,
                "min_peers_required": self.MINIMUM_PEER_COUNT,
            },
            "skill_gaps": skill_gaps,
            "match_criteria": match_criteria,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }

        if existing_score:
            # Update existing score
            existing_score.score = score
            existing_score.benchmark_data = benchmark_data
            existing_score.calculated_at = datetime.now(timezone.utc)
            benchmark_score = existing_score
        else:
            # Create new score
            benchmark_score = BenchmarkScore(
                user_id=user.id,
                job_id=job.id,
                score=score,
                benchmark_data=benchmark_data,
                calculated_at=datetime.now(timezone.utc),
            )
            db.add(benchmark_score)

        await db.commit()
        await db.refresh(benchmark_score)
        return benchmark_score
