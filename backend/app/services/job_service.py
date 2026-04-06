"""
Job Service — Business logic for job discovery and management.

Handles job deduplication, user-job matching, and status transitions.
Works with the Job Scanner agent for automated discovery.
"""

import logging
import re
from typing import Any, Optional, Tuple
from sqlalchemy import and_, desc, asc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from app.models.user import User

logger = logging.getLogger(__name__)


class JobService:
    """Handles job-related business logic.

    Methods:
        match_jobs_to_user: Score and match new jobs to a user.
        list_user_jobs: Retrieve matched jobs with filtering.
        update_status: Transition job status (new → applied, etc.).
        calculate_match_score: AI-powered job-user compatibility scoring.
    """

    def __init__(self):
        """Initialize Job Service with configuration."""
        self.min_match_score = 30  # Only create UserJob if score >= threshold
        self.max_jobs_per_user = 100  # Limit stored jobs per user

    async def match_jobs_to_user(
        self,
        user: User,
        jobs: list[ScrapedJob],
        db: AsyncSession,
    ) -> list[UserJob]:
        """Calculate match scores and create UserJob associations.

        For each job, calculates compatibility score based on user's CV data
        and job requirements. Creates UserJob records for high-scoring matches.

        Args:
            user: User to match jobs for.
            jobs: List of scraped jobs to evaluate.
            db: Database session.

        Returns:
            list[UserJob]: Created user-job associations with scores.
        """
        # Get user's active resume for skill matching
        stmt = (
            select(ParsedResume)
            .where(ParsedResume.user_id == user.id, ParsedResume.is_active == True)
            .order_by(desc(ParsedResume.created_at))
        )
        result = await db.execute(stmt)
        active_resume = result.scalar_one_or_none()

        if not active_resume:
            logger.warning(f"User {user.id} has no active resume for job matching")
            return []

        user_jobs = []
        for job in jobs:
            try:
                # Check if UserJob already exists
                stmt = select(UserJob).where(
                    and_(UserJob.user_id == user.id, UserJob.job_id == job.id)
                )
                result = await db.execute(stmt)
                if result.scalar_one_or_none():
                    continue  # Skip if association already exists

                # Calculate match score
                match_score = self._calculate_match_score(active_resume, job)

                # Only create UserJob if score meets threshold
                if match_score >= self.min_match_score:
                    user_job = UserJob(
                        user_id=user.id,
                        job_id=job.id,
                        match_score=match_score,
                        status="new",
                    )
                    db.add(user_job)
                    user_jobs.append(user_job)

                    logger.debug(
                        f"Matched job {job.job_title} @ {job.company_name} "
                        f"to user {user.id} with score {match_score}"
                    )

            except Exception as e:
                logger.error(f"Error matching job {job.id} to user {user.id}: {e}")
                continue

        # Flush to get IDs without committing
        if user_jobs:
            await db.flush()

        logger.info(f"Created {len(user_jobs)} job matches for user {user.id}")
        return user_jobs

    def _calculate_match_score(
        self,
        resume: ParsedResume,
        job: ScrapedJob,
    ) -> int:
        """Calculate job-user compatibility score (0-100).

        Uses keyword matching, skill overlap, and experience requirements
        to compute compatibility percentage.

        Args:
            resume: User's parsed resume with skills and experience.
            job: Job posting with description and requirements.

        Returns:
            int: Match score from 0-100.
        """
        score = 0
        parsed_cv = resume.parsed_data or {}

        # Extract job requirements from description
        job_requirements = self._extract_job_requirements(job.description or "")
        job_title_keywords = self._extract_keywords_from_title(job.job_title)

        # 1. Skills matching (40 points max)
        user_skills = set()
        if "skills" in parsed_cv:
            user_skills.update([s.lower() for s in parsed_cv["skills"]])
        if "technologies" in parsed_cv:
            user_skills.update([t.lower() for t in parsed_cv["technologies"]])

        skills_score = self._calculate_skills_match(user_skills, job_requirements)
        score += min(skills_score, 40)

        # 2. Job title relevance (25 points max)
        title_score = self._calculate_title_match(parsed_cv, job_title_keywords)
        score += min(title_score, 25)

        # 3. Experience level match (20 points max)
        experience_score = self._calculate_experience_match(parsed_cv, job)
        score += min(experience_score, 20)

        # 4. Company/domain match (15 points max)
        domain_score = self._calculate_domain_match(parsed_cv, job)
        score += min(domain_score, 15)

        return min(score, 100)

    def _extract_job_requirements(self, description: str) -> set[str]:
        """Extract technical skills and requirements from job description.

        Args:
            description: Job description text.

        Returns:
            set[str]: Normalized set of required skills/technologies.
        """
        if not description:
            return set()

        # Common tech skills patterns
        tech_patterns = [
            r'\b(?:python|java|javascript|typescript|react|angular|vue|node\.?js)\b',
            r'\b(?:sql|postgresql|mysql|mongodb|redis|docker|kubernetes)\b',
            r'\b(?:aws|azure|gcp|cloud|api|rest|graphql|microservices)\b',
            r'\b(?:git|agile|scrum|ci/cd|devops|linux|unix)\b',
        ]

        requirements = set()
        description_lower = description.lower()

        for pattern in tech_patterns:
            matches = re.findall(pattern, description_lower, re.IGNORECASE)
            requirements.update(matches)

        # Also look for explicit requirements sections
        req_section_match = re.search(
            r'(?:requirements?|qualifications?|skills?):?(.*?)(?:\n\n|\n[A-Z]|$)',
            description,
            re.IGNORECASE | re.DOTALL,
        )

        if req_section_match:
            req_text = req_section_match.group(1).lower()
            # Extract more skills from requirements section
            additional_matches = []
            for pattern in tech_patterns:
                additional_matches.extend(re.findall(pattern, req_text, re.IGNORECASE))
            requirements.update(additional_matches)

        return requirements

    def _extract_keywords_from_title(self, job_title: str) -> set[str]:
        """Extract relevant keywords from job title.

        Args:
            job_title: Job title string.

        Returns:
            set[str]: Normalized keywords.
        """
        if not job_title:
            return set()

        # Remove common job level indicators
        title_clean = re.sub(
            r'\b(?:senior|junior|lead|principal|staff|intern|entry.level|mid.level)\b',
            '',
            job_title.lower()
        )

        # Extract role keywords
        keywords = set()
        role_patterns = [
            r'\b(?:engineer|developer|programmer|architect|analyst|designer)\b',
            r'\b(?:frontend|backend|fullstack|full.stack|devops|qa|sre)\b',
            r'\b(?:software|web|mobile|data|ml|ai|cloud)\b',
        ]

        for pattern in role_patterns:
            matches = re.findall(pattern, title_clean)
            keywords.update(matches)

        return keywords

    def _calculate_skills_match(self, user_skills: set[str], job_requirements: set[str]) -> int:
        """Calculate skill overlap score.

        Args:
            user_skills: Set of user's skills/technologies.
            job_requirements: Set of job's required skills.

        Returns:
            int: Skills match score (0-40).
        """
        if not job_requirements:
            return 20  # Neutral score if no requirements found

        matches = len(user_skills.intersection(job_requirements))
        total_requirements = len(job_requirements)

        if total_requirements == 0:
            return 20

        match_ratio = matches / total_requirements
        return int(match_ratio * 40)

    def _calculate_title_match(self, parsed_cv: dict, job_title_keywords: set[str]) -> int:
        """Calculate job title relevance score.

        Args:
            parsed_cv: User's parsed CV data.
            job_title_keywords: Keywords from job title.

        Returns:
            int: Title relevance score (0-25).
        """
        if not job_title_keywords:
            return 15  # Neutral score

        user_experience = parsed_cv.get("experience", [])
        user_roles = set()

        for exp in user_experience:
            if isinstance(exp, dict) and "role" in exp:
                role_keywords = self._extract_keywords_from_title(exp["role"])
                user_roles.update(role_keywords)

        matches = len(user_roles.intersection(job_title_keywords))
        if matches > 0:
            return min(matches * 10, 25)  # 10 points per matching keyword

        return 5  # Base score for any experience

    def _calculate_experience_match(self, parsed_cv: dict, job: ScrapedJob) -> int:
        """Calculate experience level compatibility.

        Args:
            parsed_cv: User's parsed CV data.
            job: Job posting.

        Returns:
            int: Experience match score (0-20).
        """
        user_years = parsed_cv.get("total_years_experience", 0)
        if user_years == 0:
            return 5  # Base score for new graduates

        # Infer required experience from job title and description
        job_text = f"{job.job_title} {job.description or ''}".lower()

        if any(term in job_text for term in ["senior", "lead", "principal", "10+ years", "8+ years"]):
            required_years = 8
        elif any(term in job_text for term in ["mid-level", "5+ years", "3+ years"]):
            required_years = 3
        elif any(term in job_text for term in ["junior", "entry", "1+ year", "0-2 years"]):
            required_years = 1
        else:
            required_years = 2  # Default assumption

        # Score based on experience alignment
        if user_years >= required_years:
            if user_years <= required_years + 3:
                return 20  # Perfect match
            else:
                return 15  # Overqualified but good
        else:
            gap = required_years - user_years
            if gap <= 1:
                return 12  # Slight underqualification
            elif gap <= 3:
                return 8   # Moderate gap
            else:
                return 3   # Significant gap

    def _calculate_domain_match(self, parsed_cv: dict, job: ScrapedJob) -> int:
        """Calculate industry/domain compatibility.

        Args:
            parsed_cv: User's parsed CV data.
            job: Job posting.

        Returns:
            int: Domain match score (0-15).
        """
        # Extract user's previous company types from experience
        user_experience = parsed_cv.get("experience", [])
        job_company = job.company_name.lower()

        # Simple heuristic: if user worked at similar companies
        for exp in user_experience:
            if isinstance(exp, dict) and "company" in exp:
                user_company = exp["company"].lower()
                # Check for similar company patterns (startup, corp, etc.)
                if any(indicator in job_company and indicator in user_company
                       for indicator in ["tech", "software", "systems", "solutions", "labs"]):
                    return 15

        # Check for domain-specific technologies
        user_technologies = set()
        if "technologies" in parsed_cv:
            user_technologies.update([t.lower() for t in parsed_cv["technologies"]])

        job_description = (job.description or "").lower()

        # Domain matching: fintech, healthcare, ecommerce, etc.
        domain_indicators = {
            "fintech": ["payment", "banking", "financial", "trading", "blockchain"],
            "healthcare": ["medical", "health", "patient", "clinical", "fhir"],
            "ecommerce": ["ecommerce", "retail", "shopping", "marketplace", "payment"],
            "gaming": ["game", "gaming", "unity", "unreal", "graphics"],
        }

        for domain, keywords in domain_indicators.items():
            if any(keyword in job_description for keyword in keywords):
                # Check if user has relevant experience
                if any(tech in user_technologies for tech in keywords):
                    return 12

        return 8  # Default domain score

    async def list_user_jobs(
        self,
        user_id: str,
        db: AsyncSession,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "match_score",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[list[UserJob], int]:
        """Retrieve jobs matched to a user with filtering, search, and pagination.

        Args:
            user_id: User's UUID.
            db: Database session.
            status_filter: Filter by job status (new, applied, etc.).
            search: Case-insensitive search on job_title and company_name.
            sort_by: Column to sort by (match_score, created_at, company_name, job_title).
            sort_order: Sort direction — 'asc' or 'desc'.
            limit: Maximum number of jobs to return.
            offset: Number of records to skip (for pagination).

        Returns:
            Tuple[list[UserJob], int]: Matched jobs and total count matching the query.
        """
        # Map UI sort keys to actual columns (joining through the related ScrapedJob)
        sort_column_map = {
            "match_score": UserJob.match_score,
            "created_at": UserJob.created_at,
            "company_name": ScrapedJob.company_name,
            "job_title": ScrapedJob.job_title,
        }
        sort_col = sort_column_map.get(sort_by, UserJob.match_score)
        order_expr = asc(sort_col) if sort_order == "asc" else desc(sort_col)

        # Build base query with eager-loaded job relation
        base_stmt = (
            select(UserJob)
            .options(selectinload(UserJob.job))
            .join(ScrapedJob, UserJob.job_id == ScrapedJob.id)
            .where(UserJob.user_id == user_id)
        )

        # Apply status filter
        if status_filter:
            base_stmt = base_stmt.where(UserJob.status == status_filter)

        # Apply search filter (case-insensitive on title or company)
        if search:
            pattern = f"%{search}%"
            base_stmt = base_stmt.where(
                or_(
                    ScrapedJob.job_title.ilike(pattern),
                    ScrapedJob.company_name.ilike(pattern),
                )
            )

        # Count total matching rows (before pagination)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar_one()

        # Apply ordering and pagination
        paged_stmt = base_stmt.order_by(order_expr, desc(UserJob.created_at)).limit(limit).offset(offset)
        result = await db.execute(paged_stmt)
        jobs = list(result.scalars().all())

        return jobs, total_count

    async def update_job_status(
        self,
        user_job_id: str,
        new_status: str,
        db: AsyncSession,
    ) -> Optional[UserJob]:
        """Update the status of a user-job relationship.

        When transitioning to 'applied', automatically records `applied_at`
        timestamp so the Application History tab can show when the user applied.

        Args:
            user_job_id: UserJob UUID.
            new_status: New status value.
            db: Database session.

        Returns:
            UserJob | None: Updated user-job or None if not found.
        """
        from datetime import datetime, timezone  # local import to avoid circular

        user_job = await db.get(UserJob, user_job_id)
        if not user_job:
            return None

        user_job.status = new_status

        # Record the exact moment the user clicked "Applied"
        if new_status == "applied" and user_job.applied_at is None:
            user_job.applied_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user_job)

        logger.info(f"Updated UserJob {user_job_id} status to {new_status}")
        return user_job
