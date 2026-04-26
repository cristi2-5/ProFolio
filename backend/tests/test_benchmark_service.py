"""
Tests for the Benchmark Service (Phase 6 / Epic 5 / US 5.1 + 5.2).

The service does:
    1. Load + sanitize the requesting user's profile.
    2. Load + sanitize the peer pool (filtered by opt-in + level +/- niche).
    3. Enforce the 30-peer minimum.
    4. Compute a peer-weighted score and skill-gap ranking.
    5. Persist the result.

DB is always an AsyncMock here; we care about the orchestration logic and
the peer-average-weighted scoring math, not SQLAlchemy internals.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.models.benchmark import BenchmarkScore
from app.models.job import ScrapedJob
from app.models.resume import ParsedResume
from app.models.user import User
from app.services.benchmark_service import (
    MINIMUM_PEER_COUNT,
    BenchmarkResult,
    BenchmarkService,
    InsufficientPeersError,
    _peer_weighted_score,
)

# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def service() -> BenchmarkService:
    return BenchmarkService()


@pytest.fixture
def user() -> User:
    u = Mock(spec=User)
    u.id = uuid.uuid4()
    u.seniority_level = "mid"
    u.niche = "backend"
    u.benchmark_opt_in = True
    return u


@pytest.fixture
def job() -> ScrapedJob:
    j = Mock(spec=ScrapedJob)
    j.id = uuid.uuid4()
    j.job_title = "Mid Python Backend Engineer"
    j.company_name = "TechCorp"
    j.description = (
        "Python backend role — FastAPI, PostgreSQL, Docker. "
        "3 years experience required."
    )
    return j


@pytest.fixture
def user_resume() -> ParsedResume:
    r = Mock(spec=ParsedResume)
    r.parsed_data = {
        "skills": ["Python", "FastAPI"],
        "total_years_experience": 4,
    }
    return r


def _make_peer_row(
    *, skills: Iterable[str], niche: str = "backend", level: str = "mid"
):
    """Emulate the (level, niche, parsed_data) row the service selects."""
    return (level, niche, {"skills": list(skills)})


def _db_with(*, user_resume: Optional[ParsedResume], peer_rows: List[tuple]):
    """Build an AsyncMock db that yields the right rows in the right order.

    Order of ``execute`` calls in ``calculate_benchmark_score``:
        1. Load the active resume (``scalar_one_or_none``).
        2. Load peer rows (``all``).
        3. Look up existing BenchmarkScore row (``scalar_one_or_none``).
    """
    db = AsyncMock()
    # db.add is synchronous in SQLAlchemy; override the AsyncMock default.
    db.add = Mock()

    resume_result = MagicMock()
    resume_result.scalar_one_or_none.return_value = user_resume

    peers_result = MagicMock()
    peers_result.all.return_value = peer_rows

    upsert_result = MagicMock()
    upsert_result.scalar_one_or_none.return_value = None  # always insert

    db.execute.side_effect = [resume_result, peers_result, upsert_result]

    # db.refresh should give the row an id + calculated_at
    async def _refresh(row: Any) -> None:
        if not getattr(row, "id", None):
            row.id = uuid.uuid4()
        if not getattr(row, "calculated_at", None):
            row.calculated_at = datetime.now(timezone.utc)

    db.refresh.side_effect = _refresh
    return db


# ----------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_returns_benchmark_result_with_expected_fields(
        self, service, user, job, user_resume
    ) -> None:
        # 30 peers, all stronger than the user on FastAPI/Docker/Postgres
        peer_rows = [
            _make_peer_row(skills=["python", "fastapi", "postgresql", "docker"])
            for _ in range(MINIMUM_PEER_COUNT)
        ]
        db = _db_with(user_resume=user_resume, peer_rows=peer_rows)

        result = await service.calculate_benchmark_score(user=user, job=job, db=db)

        assert isinstance(result, BenchmarkResult)
        assert 0 <= result.score <= 100
        assert result.peer_group_size == MINIMUM_PEER_COUNT
        assert result.seniority_level == "mid"
        assert result.niche == "backend"
        # User has Python+FastAPI; JD needs Python+FastAPI+PostgreSQL+Docker
        # → user_match = 2/4 = 0.5; peer_mean = 4/4 = 1.0 → score < 50
        assert result.user_match_score == pytest.approx(0.5, abs=0.01)
        assert result.peer_mean_match_score == pytest.approx(1.0, abs=0.01)
        assert result.score < 50

    @pytest.mark.asyncio
    async def test_top_missing_skills_ranked_by_peer_frequency(
        self, service, user, job, user_resume
    ) -> None:
        # 10 peers have Docker, 20 have PostgreSQL, 5 have AWS (but AWS not in JD).
        peer_rows = [
            _make_peer_row(skills=["python", "fastapi", "docker"]) for _ in range(10)
        ] + [
            _make_peer_row(skills=["python", "fastapi", "postgresql"])
            for _ in range(20)
        ]
        db = _db_with(user_resume=user_resume, peer_rows=peer_rows)

        result = await service.calculate_benchmark_score(user=user, job=job, db=db)

        # postgresql held by 20/30 = 0.67; docker by 10/30 = 0.33
        skills = [gap["skill"] for gap in result.missing_skills]
        assert skills[0] == "postgresql"
        assert result.missing_skills[0]["peer_frequency"] == pytest.approx(
            0.667, abs=0.01
        )
        assert "docker" in skills

    @pytest.mark.asyncio
    async def test_recommended_keywords_covers_all_required(
        self, service, user, job, user_resume
    ) -> None:
        peer_rows = [
            _make_peer_row(skills=["python", "fastapi", "postgresql", "docker"])
            for _ in range(MINIMUM_PEER_COUNT)
        ]
        db = _db_with(user_resume=user_resume, peer_rows=peer_rows)

        result = await service.calculate_benchmark_score(user=user, job=job, db=db)

        assert set(result.recommended_keywords) >= {
            "python",
            "fastapi",
            "postgresql",
            "docker",
        }
        assert "python" in result.matched_skills
        assert "fastapi" in result.matched_skills


# ----------------------------------------------------------------------
# Enforcement paths
# ----------------------------------------------------------------------


class TestEnforcement:
    @pytest.mark.asyncio
    async def test_requires_opt_in(self, service, user, job) -> None:
        user.benchmark_opt_in = False
        with pytest.raises(ValueError, match="opted into benchmarking"):
            await service.calculate_benchmark_score(user=user, job=job, db=AsyncMock())

    @pytest.mark.asyncio
    async def test_mid_senior_must_set_niche(self, service, user, job) -> None:
        user.niche = None
        with pytest.raises(ValueError, match="niche"):
            await service.calculate_benchmark_score(user=user, job=job, db=AsyncMock())

    @pytest.mark.asyncio
    async def test_junior_without_niche_is_fine(
        self, service, user, job, user_resume
    ) -> None:
        user.seniority_level = "junior"
        user.niche = None
        peer_rows = [
            _make_peer_row(skills=["python", "fastapi"], niche=None, level="junior")
            for _ in range(MINIMUM_PEER_COUNT)
        ]
        db = _db_with(user_resume=user_resume, peer_rows=peer_rows)
        result = await service.calculate_benchmark_score(user=user, job=job, db=db)
        assert result.seniority_level == "junior"

    @pytest.mark.asyncio
    async def test_insufficient_peers_raises(
        self, service, user, job, user_resume
    ) -> None:
        peer_rows = [
            _make_peer_row(skills=["python"]) for _ in range(MINIMUM_PEER_COUNT - 1)
        ]
        db = _db_with(user_resume=user_resume, peer_rows=peer_rows)

        with pytest.raises(InsufficientPeersError) as exc_info:
            await service.calculate_benchmark_score(user=user, job=job, db=db)
        assert exc_info.value.peers_found == MINIMUM_PEER_COUNT - 1
        assert exc_info.value.peers_required == MINIMUM_PEER_COUNT

    @pytest.mark.asyncio
    async def test_missing_active_resume_raises(self, service, user, job) -> None:
        db = _db_with(user_resume=None, peer_rows=[])
        with pytest.raises(ValueError, match="active resume"):
            await service.calculate_benchmark_score(user=user, job=job, db=db)


# ----------------------------------------------------------------------
# Scoring math
# ----------------------------------------------------------------------


class TestPeerWeightedScore:
    """Pure-function tests for ``_peer_weighted_score``."""

    def test_user_equals_peer_mean_yields_50(self) -> None:
        assert _peer_weighted_score(0.5, 0.5) == 50
        assert _peer_weighted_score(1.0, 1.0) == 50

    def test_user_above_mean_gets_higher_score(self) -> None:
        assert _peer_weighted_score(1.0, 0.5) == 75

    def test_user_below_mean_gets_lower_score(self) -> None:
        assert _peer_weighted_score(0.0, 0.5) == 25

    def test_clamped_to_bounds(self) -> None:
        assert _peer_weighted_score(1.0, 0.0) == 100
        assert _peer_weighted_score(0.0, 1.0) == 0

    def test_nan_falls_back_to_50(self) -> None:
        assert _peer_weighted_score(float("nan"), 0.5) == 50
        assert _peer_weighted_score(0.5, float("nan")) == 50
