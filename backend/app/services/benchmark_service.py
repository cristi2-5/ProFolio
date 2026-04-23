"""
Benchmark Service — competitive scoring for a single (user, job) pair.

GDPR-compliant: peer data flows through ``benchmark_sanitizer`` so user
IDs and PII never reach the aggregation path. Opt-in is strictly
enforced. Peer grouping is by ``user.seniority_level`` (always) plus
``user.niche`` for mid/senior. Below the 30-peer minimum, raises
``InsufficientPeersError`` so the router can surface a warning instead
of a score.

The final score blends the user's raw JD-match with the peer average:

        score = round(50 + 50 * (user_match - peer_mean))

so a user who matches the JD exactly as well as the average peer lands
at 50 and movements in either direction are symmetric around 0.5.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benchmark import BenchmarkScore
from app.models.job import ScrapedJob
from app.models.user import User
from app.services.peer_data import (
    MID_SENIOR_LEVELS,
    load_active_resume,
    load_peer_profiles,
)
from app.utils.benchmark_sanitizer import (
    JobRequirements,
    SanitizedProfile,
    extract_job_requirements,
    sanitize_profile,
    skill_coverage_ratio,
    skill_gap,
)

logger = logging.getLogger(__name__)

MINIMUM_PEER_COUNT = 30


class InsufficientPeersError(Exception):
    """Raised when fewer than MINIMUM_PEER_COUNT eligible peers exist."""

    def __init__(self, peers_found: int, peers_required: int = MINIMUM_PEER_COUNT):
        self.peers_found = peers_found
        self.peers_required = peers_required
        super().__init__(
            f"Insufficient peer data: {peers_found} peers found, "
            f"minimum {peers_required} required"
        )


@dataclass
class BenchmarkResult:
    """Structured result returned to the router layer.

    Kept separate from the ORM row so the router can build a response
    without re-parsing JSONB columns. The persisted row captures the same
    data.
    """

    score: int
    user_match_score: float
    peer_mean_match_score: float
    peer_group_size: int
    seniority_level: Optional[str]
    niche: Optional[str]
    missing_skills: List[Dict[str, Any]]
    matched_skills: List[str]
    recommended_keywords: List[str]
    calculated_at: datetime
    benchmark_id: str


class BenchmarkService:
    """Coordinates sanitization, peer aggregation, scoring, and persistence."""

    MINIMUM_PEER_COUNT = MINIMUM_PEER_COUNT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def calculate_benchmark_score(
        self,
        *,
        user: User,
        job: ScrapedJob,
        db: AsyncSession,
    ) -> BenchmarkResult:
        """Compute and persist a benchmark score for one (user, job) pair.

        Raises:
            ValueError: If the user has not opted in or lacks a parsed CV.
            InsufficientPeersError: If the peer pool is too small.
        """
        if not user.benchmark_opt_in:
            raise ValueError("User has not opted into benchmarking")
        if user.seniority_level in MID_SENIOR_LEVELS and not user.niche:
            raise ValueError(
                "Mid/senior users must configure their niche before benchmarking"
            )

        user_resume = await load_active_resume(user, db)
        if not user_resume or not user_resume.parsed_data:
            raise ValueError("User has no active resume; cannot benchmark")

        user_profile = sanitize_profile(
            seniority_level=user.seniority_level,
            niche=user.niche,
            parsed_resume=user_resume.parsed_data,
        )
        requirements = extract_job_requirements(job.description or "")

        peer_profiles = await load_peer_profiles(user=user, db=db)

        if len(peer_profiles) < self.MINIMUM_PEER_COUNT:
            raise InsufficientPeersError(peers_found=len(peer_profiles))

        user_match = skill_coverage_ratio(user_profile, requirements)
        peer_matches = [skill_coverage_ratio(p, requirements) for p in peer_profiles]
        peer_mean = sum(peer_matches) / len(peer_matches)

        score = _peer_weighted_score(user_match, peer_mean)

        missing = self._rank_missing_skills(user_profile, requirements, peer_profiles)
        matched = sorted(requirements.required_skills & user_profile.skills)
        recommended_keywords = self._recommended_keywords(requirements, user_profile)

        benchmark_row = await self._upsert_benchmark_row(
            user=user,
            job=job,
            score=score,
            peer_group_size=len(peer_profiles),
            missing_skills=missing,
            recommended_keywords=recommended_keywords,
            matched_skills=matched,
            user_match_score=user_match,
            peer_mean_match_score=peer_mean,
            db=db,
        )

        logger.info(
            "Benchmark calculated user=%s job=%s score=%d peers=%d",
            user.id, job.id, score, len(peer_profiles),
        )

        return BenchmarkResult(
            score=score,
            user_match_score=user_match,
            peer_mean_match_score=peer_mean,
            peer_group_size=len(peer_profiles),
            seniority_level=user.seniority_level,
            niche=user.niche,
            missing_skills=missing,
            matched_skills=matched,
            recommended_keywords=recommended_keywords,
            calculated_at=benchmark_row.calculated_at,
            benchmark_id=str(benchmark_row.id),
        )

    # ------------------------------------------------------------------
    # Skill-gap analytics (US 5.2 + feeds US 5.3 single-job recommendations)
    # ------------------------------------------------------------------

    @staticmethod
    def _rank_missing_skills(
        user_profile: SanitizedProfile,
        requirements: JobRequirements,
        peer_profiles: List[SanitizedProfile],
    ) -> List[Dict[str, Any]]:
        """Top 3 missing skills ordered by peer-group frequency.

        Frequency drives priority: if 80% of peers at this level/niche
        have a skill the user lacks, it's a high-priority gap.
        """
        gaps = skill_gap(user_profile, requirements)
        if not gaps or not peer_profiles:
            return []

        total_peers = len(peer_profiles)
        ranked: List[Dict[str, Any]] = []
        for skill in gaps:
            peers_with = sum(1 for p in peer_profiles if p.has_skill(skill))
            frequency = peers_with / total_peers
            ranked.append(
                {
                    "skill": skill,
                    "peer_frequency": round(frequency, 3),
                    "priority": _priority_for(frequency),
                    "recommendation": _recommendation_for(skill),
                }
            )
        ranked.sort(key=lambda item: (-item["peer_frequency"], item["skill"]))
        return ranked[:3]

    @staticmethod
    def _recommended_keywords(
        requirements: JobRequirements, user_profile: SanitizedProfile
    ) -> List[str]:
        """ATS keywords the user should surface: required skills, prioritizing gaps."""
        missing = sorted(requirements.required_skills - user_profile.skills)
        matched = sorted(requirements.required_skills & user_profile.skills)
        return missing + matched

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _upsert_benchmark_row(
        self,
        *,
        user: User,
        job: ScrapedJob,
        score: int,
        peer_group_size: int,
        missing_skills: List[Dict[str, Any]],
        recommended_keywords: List[str],
        matched_skills: List[str],
        user_match_score: float,
        peer_mean_match_score: float,
        db: AsyncSession,
    ) -> BenchmarkScore:
        """Insert or update the BenchmarkScore row for this (user, job)."""
        stmt = select(BenchmarkScore).where(
            BenchmarkScore.user_id == user.id,
            BenchmarkScore.job_id == job.id,
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        missing_payload = {"items": missing_skills}
        keywords_payload = {
            "items": recommended_keywords,
            "matched": matched_skills,
            "user_match_score": round(user_match_score, 4),
            "peer_mean_match_score": round(peer_mean_match_score, 4),
        }

        if row is None:
            row = BenchmarkScore(
                user_id=user.id,
                job_id=job.id,
                score=score,
                peer_group_size=peer_group_size,
                seniority_level=user.seniority_level,
                niche=user.niche,
                missing_skills=missing_payload,
                recommended_keywords=keywords_payload,
                calculated_at=datetime.now(timezone.utc),
            )
            db.add(row)
        else:
            row.score = score
            row.peer_group_size = peer_group_size
            row.seniority_level = user.seniority_level
            row.niche = user.niche
            row.missing_skills = missing_payload
            row.recommended_keywords = keywords_payload
            row.calculated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(row)
        return row


# ----------------------------------------------------------------------
# Pure helpers
# ----------------------------------------------------------------------


def _peer_weighted_score(user_match: float, peer_mean: float) -> int:
    """Map user_match + peer_mean into a 0-100 score centred on 50.

    score = 50 + 50 * (user_match - peer_mean), clamped to [0, 100].

    At user == peer_mean we land exactly at 50. A user fully covering the
    JD when peers average 0.5 lands at 75; a user at 0 when peers average
    0.5 lands at 25. Boundaries clamp but shouldn't normally hit them.
    """
    if math.isnan(user_match) or math.isnan(peer_mean):
        return 50
    raw = 50 + 50 * (user_match - peer_mean)
    return max(0, min(100, round(raw)))


def _priority_for(frequency: float) -> str:
    if frequency >= 0.7:
        return "high"
    if frequency >= 0.4:
        return "medium"
    return "low"


def _recommendation_for(skill: str) -> str:
    """Human-readable suggestion for a missing skill."""
    tips = {
        "react": "Work through the official React tutorial and ship one small SPA.",
        "typescript": "Convert an existing JS project incrementally to TS.",
        "python": "Cover the official tutorial, then build one CLI with type hints.",
        "aws": "Target the AWS Cloud Practitioner exam as a learning milestone.",
        "docker": "Containerise an existing project end-to-end (dev + prod image).",
        "kubernetes": "Start with a local minikube cluster; deploy one multi-service app.",
        "postgresql": "Practise joins, window functions, and EXPLAIN on a real dataset.",
        "fastapi": "Build a small CRUD API with async SQLAlchemy + JWT auth.",
    }
    return tips.get(
        skill.lower(),
        f"Study {skill} via its official docs and ship one small project using it.",
    )
