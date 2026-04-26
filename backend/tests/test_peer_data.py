"""
Tests for the peer-data loader (Phase 6 / Epic 5 / US 5.1).

These tests act as a regression guard for the GDPR contract of the
benchmark subsystem. They focus on three load-bearing invariants:

    1. The sanitized output never carries identifying fields — only
       ``seniority_level``, ``niche``, ``years_experience``, ``skills``.
    2. Peers with ``benchmark_opt_in == False`` are excluded from the
       peer pool — even if they otherwise match the requesting user.
    3. The 30-peer minimum threshold is enforced at the service layer
       and surfaces as ``InsufficientPeersError``.

We rely on the real Postgres test database (via ``test_session`` from
conftest) so the SQL filters are exercised end-to-end rather than
mocked away.
"""

from __future__ import annotations

import uuid
from dataclasses import fields
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.job import ScrapedJob
from app.models.resume import ParsedResume
from app.models.user import User
from app.services.benchmark_service import (
    MINIMUM_PEER_COUNT,
    BenchmarkService,
    InsufficientPeersError,
)
from app.services.peer_data import load_peer_profiles
from app.utils.benchmark_sanitizer import SanitizedProfile


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


async def _create_user(
    session,
    *,
    email: str,
    seniority_level: str = "mid",
    niche: str | None = "backend",
    benchmark_opt_in: bool = True,
) -> User:
    """Insert a user with a hashed-password placeholder."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash="not-a-real-hash",
        full_name="Test User",
        seniority_level=seniority_level,
        niche=niche,
        benchmark_opt_in=benchmark_opt_in,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_resume(
    session,
    *,
    user: User,
    parsed_data: Dict[str, Any] | None = None,
    is_active: bool = True,
) -> ParsedResume:
    resume = ParsedResume(
        id=uuid.uuid4(),
        user_id=user.id,
        original_filename="cv.pdf",
        file_url="uploads/cv.pdf",
        parsed_data=parsed_data or {"skills": ["Python", "FastAPI"]},
        is_active=is_active,
    )
    session.add(resume)
    await session.flush()
    return resume


# ----------------------------------------------------------------------
# 1. Sanitized output shape — only expected keys, no PII
# ----------------------------------------------------------------------


class TestSanitizedProfileShape:
    """The sanitizer's output must never expose user identity."""

    def test_only_expected_fields_on_dataclass(self) -> None:
        """``SanitizedProfile`` schema lists exactly the four agreed fields.

        This is the structural guarantee the GDPR claims rest on — if
        someone adds ``user_id`` or ``email`` to the dataclass this test
        fails loudly before the change can ship.
        """
        names = {f.name for f in fields(SanitizedProfile)}
        assert names == {
            "seniority_level",
            "niche",
            "years_experience",
            "skills",
        }

    def test_forbidden_fields_are_absent(self) -> None:
        """Belt-and-braces guard against PII fields creeping in."""
        names = {f.name for f in fields(SanitizedProfile)}
        forbidden = {
            "user_id",
            "id",
            "email",
            "name",
            "full_name",
            "phone",
            "address",
            "company",
            "role",
        }
        assert forbidden.isdisjoint(names)


# ----------------------------------------------------------------------
# 2. Opt-out exclusion — load_peer_profiles must filter on benchmark_opt_in
# ----------------------------------------------------------------------


class TestPeerOptOutFiltering:
    """``benchmark_opt_in`` must gate inclusion in the peer pool."""

    async def test_opted_out_user_is_excluded(self, test_session) -> None:
        """A user with ``benchmark_opt_in=False`` must never appear as a peer.

        We seed:
            * one requesting user (irrelevant to results — never in own pool)
            * one opt-IN peer (should appear)
            * one opt-OUT peer with otherwise-identical profile (must NOT)

        and assert the loader returned exactly one sanitized profile.
        """
        requester = await _create_user(
            test_session, email=f"req-{uuid.uuid4()}@test.com"
        )
        await _create_resume(test_session, user=requester)

        opt_in_peer = await _create_user(
            test_session,
            email=f"opt-in-{uuid.uuid4()}@test.com",
            benchmark_opt_in=True,
        )
        await _create_resume(test_session, user=opt_in_peer)

        opt_out_peer = await _create_user(
            test_session,
            email=f"opt-out-{uuid.uuid4()}@test.com",
            benchmark_opt_in=False,
        )
        await _create_resume(test_session, user=opt_out_peer)

        await test_session.commit()

        peers = await load_peer_profiles(user=requester, db=test_session)

        # Exactly one peer — the opt-out user must be filtered out.
        assert len(peers) == 1
        # And the survivor must have the expected (anonymous) shape.
        assert isinstance(peers[0], SanitizedProfile)

    async def test_requesting_user_is_excluded_from_own_pool(
        self, test_session
    ) -> None:
        """A user must not benchmark against themselves."""
        requester = await _create_user(
            test_session, email=f"self-{uuid.uuid4()}@test.com"
        )
        await _create_resume(test_session, user=requester)
        await test_session.commit()

        peers = await load_peer_profiles(user=requester, db=test_session)
        assert peers == []


# ----------------------------------------------------------------------
# 3. Threshold of 30 is enforced before scoring
# ----------------------------------------------------------------------


class TestMinimumPeerThreshold:
    """``BenchmarkService`` must refuse to score below the 30-peer floor."""

    async def test_under_threshold_raises_insufficient_peers(self) -> None:
        """A peer pool of N < 30 raises ``InsufficientPeersError``.

        We patch ``load_peer_profiles`` so the service sees a
        deterministically small pool — the goal here is to verify the
        threshold gate, not the SQL itself (covered above).
        """
        from app.services import benchmark_service as svc_module

        service = BenchmarkService()

        user = Mock(spec=User)
        user.id = uuid.uuid4()
        user.seniority_level = "mid"
        user.niche = "backend"
        user.benchmark_opt_in = True

        job = Mock(spec=ScrapedJob)
        job.id = uuid.uuid4()
        job.description = "Python backend role — FastAPI, PostgreSQL."

        # Active resume for the requester (real-ish parsed_data is fine).
        resume = Mock(spec=ParsedResume)
        resume.parsed_data = {"skills": ["Python", "FastAPI"]}

        # 29 peers — one short of the floor.
        small_pool = [
            SanitizedProfile(
                seniority_level="mid",
                niche="backend",
                years_experience=3.0,
                skills=frozenset({"python", "fastapi"}),
            )
            for _ in range(MINIMUM_PEER_COUNT - 1)
        ]

        db = AsyncMock()

        # Patch the two collaborators the service pulls from peer_data.
        original_load_resume = svc_module.load_active_resume
        original_load_peers = svc_module.load_peer_profiles

        async def fake_load_resume(*args, **kwargs):
            return resume

        async def fake_load_peers(*args, **kwargs):
            return small_pool

        svc_module.load_active_resume = fake_load_resume
        svc_module.load_peer_profiles = fake_load_peers
        try:
            with pytest.raises(InsufficientPeersError) as excinfo:
                await service.calculate_benchmark_score(user=user, job=job, db=db)
        finally:
            svc_module.load_active_resume = original_load_resume
            svc_module.load_peer_profiles = original_load_peers

        assert excinfo.value.peers_found == MINIMUM_PEER_COUNT - 1
        assert excinfo.value.peers_required == MINIMUM_PEER_COUNT
