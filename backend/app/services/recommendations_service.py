"""
Recommendations Service — cross-JD skill-gap analysis.

Aggregates Set A − Set B across every job the user has saved or been
matched to, then returns:

    * Top 3 missing skills, weighted by how often each skill shows up
      across the user's saved JDs and by how many peers at the same
      seniority/niche already have it.
    * Recommended ATS keywords for the CV: the skills that would move
      the needle most if added.

Pulls peer frequency data through the same ``benchmark_sanitizer`` path
the scoring service uses, so GDPR guarantees propagate end-to-end.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import ScrapedJob, UserJob
from app.models.user import User
from app.services.benchmark_service import MINIMUM_PEER_COUNT
from app.services.peer_data import load_active_resume, load_peer_profiles
from app.utils.benchmark_sanitizer import (
    SanitizedProfile,
    extract_job_requirements,
    sanitize_profile,
)

logger = logging.getLogger(__name__)

_TOP_SKILL_LIMIT = 3
_TOP_KEYWORD_LIMIT = 10
_RELEVANT_STATUSES = frozenset({"new", "saved", "applied"})


@dataclass
class RecommendationResult:
    """Payload returned to the router."""

    top_missing_skills: List[Dict[str, object]]
    recommended_keywords: List[Dict[str, object]]
    jobs_analyzed: int
    peer_group_size: int
    insufficient_peers: bool


class RecommendationsService:
    """Cross-JD skill-gap analysis (US 5.3).

    Independent from ``BenchmarkService`` on purpose — the benchmark
    service scores a single (user, job) pair, while this one answers the
    different question "given everything I'm applying for, what should I
    learn next?".
    """

    MINIMUM_PEER_COUNT = MINIMUM_PEER_COUNT

    async def generate_recommendations(
        self,
        *,
        user: User,
        db: AsyncSession,
    ) -> RecommendationResult:
        """Build recommendations from the user's saved job pool."""
        resume = await load_active_resume(user, db)
        if not resume or not resume.parsed_data:
            raise ValueError("User has no active resume; cannot recommend skills")
        user_profile = sanitize_profile(
            seniority_level=user.seniority_level,
            niche=user.niche,
            parsed_resume=resume.parsed_data,
        )

        jobs = await self._load_relevant_jobs(user, db)
        if not jobs:
            return RecommendationResult(
                top_missing_skills=[],
                recommended_keywords=[],
                jobs_analyzed=0,
                peer_group_size=0,
                insufficient_peers=False,
            )

        jd_frequency = _count_skill_demand(jobs, user_profile)
        peer_profiles = await load_peer_profiles(user=user, db=db)

        insufficient_peers = len(peer_profiles) < self.MINIMUM_PEER_COUNT
        peer_frequency = _peer_skill_frequency(peer_profiles)

        top_missing = _rank_missing_skills(
            jd_frequency=jd_frequency,
            peer_frequency=peer_frequency,
            user_profile=user_profile,
        )

        recommended_keywords = _rank_recommended_keywords(
            jd_frequency=jd_frequency,
            user_profile=user_profile,
        )

        return RecommendationResult(
            top_missing_skills=top_missing[:_TOP_SKILL_LIMIT],
            recommended_keywords=recommended_keywords[:_TOP_KEYWORD_LIMIT],
            jobs_analyzed=len(jobs),
            peer_group_size=len(peer_profiles),
            insufficient_peers=insufficient_peers,
        )

    async def _load_relevant_jobs(
        self, user: User, db: AsyncSession
    ) -> List[ScrapedJob]:
        """Jobs the user has engaged with — excludes hidden/duplicate."""
        stmt = (
            select(ScrapedJob)
            .join(UserJob, UserJob.job_id == ScrapedJob.id)
            .where(
                UserJob.user_id == user.id,
                UserJob.status.in_(_RELEVANT_STATUSES),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


# ----------------------------------------------------------------------
# Pure helpers
# ----------------------------------------------------------------------


def _count_skill_demand(
    jobs: List[ScrapedJob], user_profile: SanitizedProfile
) -> Dict[str, int]:
    """How many of the user's saved JDs require each skill."""
    counts: Dict[str, int] = {}
    for job in jobs:
        requirements = extract_job_requirements(job.description or "")
        for skill in requirements.required_skills:
            counts[skill] = counts.get(skill, 0) + 1
    return counts


def _peer_skill_frequency(
    peer_profiles: List[SanitizedProfile],
) -> Dict[str, float]:
    """Fraction of peers that have each skill (0.0 when no peers)."""
    if not peer_profiles:
        return {}
    total = len(peer_profiles)
    counts: Dict[str, int] = {}
    for profile in peer_profiles:
        for skill in profile.skills:
            counts[skill] = counts.get(skill, 0) + 1
    return {skill: count / total for skill, count in counts.items()}


def _rank_missing_skills(
    *,
    jd_frequency: Dict[str, int],
    peer_frequency: Dict[str, float],
    user_profile: SanitizedProfile,
) -> List[Dict[str, object]]:
    """Order missing skills by ``jd_count * (1 + peer_frequency)``.

    Multiplying by ``1 + peer_frequency`` breaks ties in favour of skills
    that are both in-demand across the user's JD pool AND widely held by
    peers — the classic "you're behind the curve" signal.
    """
    missing: List[Dict[str, object]] = []
    for skill, jd_count in jd_frequency.items():
        if user_profile.has_skill(skill):
            continue
        peer_freq = peer_frequency.get(skill, 0.0)
        weight = jd_count * (1.0 + peer_freq)
        missing.append(
            {
                "skill": skill,
                "jd_count": jd_count,
                "peer_frequency": round(peer_freq, 3),
                "weight": round(weight, 3),
                "priority": _priority_for(peer_freq),
                "justification": _justification(skill, jd_count, peer_freq),
            }
        )
    missing.sort(key=lambda item: (-item["weight"], item["skill"]))
    return missing


def _rank_recommended_keywords(
    *,
    jd_frequency: Dict[str, int],
    user_profile: SanitizedProfile,
) -> List[Dict[str, object]]:
    """ATS keyword suggestions: most-demanded skills first.

    Includes both missing and matched skills so the CV can be rewritten
    to surface them prominently (the CV optimizer uses exactly this kind
    of signal).
    """
    keywords: List[Dict[str, object]] = []
    for skill, jd_count in jd_frequency.items():
        keywords.append(
            {
                "keyword": skill,
                "jd_count": jd_count,
                "in_cv": user_profile.has_skill(skill),
            }
        )
    keywords.sort(key=lambda item: (-item["jd_count"], item["keyword"]))
    return keywords


def _priority_for(frequency: float) -> str:
    if frequency >= 0.7:
        return "high"
    if frequency >= 0.4:
        return "medium"
    return "low"


def _justification(skill: str, jd_count: int, peer_freq: float) -> str:
    """Short explanation a human would write next to a skill gap."""
    jd_part = (
        f"Requested in {jd_count} of your saved jobs"
        if jd_count > 1
        else "Requested in a saved job"
    )
    if peer_freq <= 0:
        return f"{jd_part}."
    pct = round(peer_freq * 100)
    return f"{jd_part}; {pct}% of peers at your level already list it."
