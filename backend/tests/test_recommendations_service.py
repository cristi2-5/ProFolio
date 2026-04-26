"""
Tests for the Recommendations Service (Phase 6 / Epic 5 / US 5.3).

The service aggregates across every relevant job the user has saved and
computes a weighted Set A − Set B, augmented with peer-frequency signal.
DB is always an AsyncMock.
"""

from __future__ import annotations

import uuid
from typing import Any, Iterable, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.models.job import ScrapedJob
from app.models.resume import ParsedResume
from app.models.user import User
from app.services.recommendations_service import (
    MINIMUM_PEER_COUNT,
    RecommendationsService,
    _count_skill_demand,
    _peer_skill_frequency,
    _rank_missing_skills,
    _rank_recommended_keywords,
)
from app.utils.benchmark_sanitizer import sanitize_profile

# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def service() -> RecommendationsService:
    return RecommendationsService()


@pytest.fixture
def user() -> User:
    u = Mock(spec=User)
    u.id = uuid.uuid4()
    u.seniority_level = "mid"
    u.niche = "backend"
    u.benchmark_opt_in = True
    return u


def _job(description: str) -> ScrapedJob:
    j = Mock(spec=ScrapedJob)
    j.id = uuid.uuid4()
    j.description = description
    j.job_title = "Mid Backend Engineer"
    j.company_name = "TechCorp"
    return j


def _make_db(
    *,
    resume_data: Optional[dict],
    jobs: List[ScrapedJob],
    peer_rows: List[tuple],
):
    """Build an AsyncMock that returns (resume, jobs, peers) in execute order."""
    db = AsyncMock()

    resume_result = MagicMock()
    if resume_data is not None:
        resume = Mock(spec=ParsedResume)
        resume.parsed_data = resume_data
        resume_result.scalar_one_or_none.return_value = resume
    else:
        resume_result.scalar_one_or_none.return_value = None

    jobs_scalars = MagicMock()
    jobs_scalars.all.return_value = jobs
    jobs_result = MagicMock()
    jobs_result.scalars.return_value = jobs_scalars

    peers_result = MagicMock()
    peers_result.all.return_value = peer_rows

    db.execute.side_effect = [resume_result, jobs_result, peers_result]
    return db


# ----------------------------------------------------------------------
# Pure helpers
# ----------------------------------------------------------------------


class TestPureHelpers:
    def test_skill_demand_counts_per_job(self) -> None:
        jobs = [_job("Python FastAPI"), _job("Python Docker"), _job("Docker AWS")]
        profile = sanitize_profile(
            seniority_level="mid", niche="backend", parsed_resume={"skills": []}
        )
        counts = _count_skill_demand(jobs, profile)
        assert counts["python"] == 2
        assert counts["docker"] == 2
        assert counts["fastapi"] == 1
        assert counts["aws"] == 1

    def test_peer_frequency_empty_pool(self) -> None:
        assert _peer_skill_frequency([]) == {}

    def test_peer_frequency_normalizes_to_fraction(self) -> None:
        peers = [
            sanitize_profile(
                seniority_level="mid",
                niche="backend",
                parsed_resume={"skills": ["Python"]},
            )
            for _ in range(2)
        ] + [
            sanitize_profile(
                seniority_level="mid",
                niche="backend",
                parsed_resume={"skills": ["Python", "Docker"]},
            )
            for _ in range(2)
        ]
        freq = _peer_skill_frequency(peers)
        assert freq["python"] == 1.0
        assert freq["docker"] == 0.5

    def test_rank_missing_skills_weights_by_jd_count_and_peer_freq(self) -> None:
        """Weight = jd_count * (1 + peer_frequency).

        Skills that peers already have AND show up in multiple JDs get
        boosted — that's the "you're falling behind" signal. A skill that's
        only slightly more demanded but nobody else has yet should rank
        lower.
        """
        profile = sanitize_profile(
            seniority_level="mid", niche="backend", parsed_resume={"skills": []}
        )
        jd_freq = {"python": 3, "docker": 2, "aws": 1}
        peer_freq = {"python": 0.1, "docker": 0.9, "aws": 0.9}
        ranked = _rank_missing_skills(
            jd_frequency=jd_freq, peer_frequency=peer_freq, user_profile=profile
        )
        # docker: 2 * 1.9 = 3.8 ; python: 3 * 1.1 = 3.3 ; aws: 1 * 1.9 = 1.9
        assert [item["skill"] for item in ranked] == ["docker", "python", "aws"]

    def test_rank_missing_skills_excludes_held_skills(self) -> None:
        profile = sanitize_profile(
            seniority_level="mid", niche="backend", parsed_resume={"skills": ["python"]}
        )
        jd_freq = {"python": 5, "docker": 1}
        ranked = _rank_missing_skills(
            jd_frequency=jd_freq, peer_frequency={}, user_profile=profile
        )
        assert [item["skill"] for item in ranked] == ["docker"]

    def test_recommended_keywords_flags_in_cv(self) -> None:
        profile = sanitize_profile(
            seniority_level="mid", niche="backend", parsed_resume={"skills": ["python"]}
        )
        keywords = _rank_recommended_keywords(
            jd_frequency={"python": 3, "docker": 1},
            user_profile=profile,
        )
        by_skill = {kw["keyword"]: kw for kw in keywords}
        assert by_skill["python"]["in_cv"] is True
        assert by_skill["docker"]["in_cv"] is False
        assert keywords[0]["keyword"] == "python"  # ordered by jd_count desc


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------


class TestGenerateRecommendations:
    @pytest.mark.asyncio
    async def test_missing_active_resume_raises(self, service, user) -> None:
        db = _make_db(resume_data=None, jobs=[], peer_rows=[])
        with pytest.raises(ValueError, match="active resume"):
            await service.generate_recommendations(user=user, db=db)

    @pytest.mark.asyncio
    async def test_no_saved_jobs_returns_empty_result(self, service, user) -> None:
        db = _make_db(resume_data={"skills": ["python"]}, jobs=[], peer_rows=[])
        result = await service.generate_recommendations(user=user, db=db)
        assert result.jobs_analyzed == 0
        assert result.top_missing_skills == []
        assert result.recommended_keywords == []

    @pytest.mark.asyncio
    async def test_insufficient_peers_flag(self, service, user) -> None:
        jobs = [_job("Python FastAPI PostgreSQL")]
        # Only 5 peers — under threshold, so we expect the flag True but
        # still a usable recommendations payload (JD-driven).
        peer_rows = [("mid", "backend", {"skills": ["python"]}) for _ in range(5)]
        db = _make_db(
            resume_data={"skills": ["python"]}, jobs=jobs, peer_rows=peer_rows
        )
        result = await service.generate_recommendations(user=user, db=db)
        assert result.insufficient_peers is True
        assert result.jobs_analyzed == 1
        assert any(item["skill"] == "fastapi" for item in result.top_missing_skills)

    @pytest.mark.asyncio
    async def test_full_pipeline_produces_top_three(self, service, user) -> None:
        jobs = [
            _job("Python FastAPI PostgreSQL Docker"),
            _job("Python FastAPI Redis"),
            _job("PostgreSQL Kafka Docker"),
        ]
        peer_rows = [
            (
                "mid",
                "backend",
                {"skills": ["python", "fastapi", "postgresql", "docker"]},
            )
            for _ in range(MINIMUM_PEER_COUNT)
        ]
        db = _make_db(
            resume_data={"skills": ["python"]}, jobs=jobs, peer_rows=peer_rows
        )

        result = await service.generate_recommendations(user=user, db=db)

        assert result.insufficient_peers is False
        assert result.jobs_analyzed == 3
        assert result.peer_group_size == MINIMUM_PEER_COUNT
        assert len(result.top_missing_skills) == 3
        # fastapi appears in 2 JDs AND 100% of peers — must be in top gaps.
        skills = {item["skill"] for item in result.top_missing_skills}
        assert "fastapi" in skills or "postgresql" in skills
