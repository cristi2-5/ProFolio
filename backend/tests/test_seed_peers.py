"""Tests for the dev-only seed_peers script.

Verifies:
- A clean DB ends up with exactly 90 peers, evenly split 30/30/30 across
  junior/mid/senior.
- Every peer is opted in to benchmarking and has one active ParsedResume.
- Re-running the seed is idempotent (no duplicates).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import ParsedResume
from app.models.user import User
from app.scripts.seed_peers import PEER_COUNT, SEED_EMAIL_DOMAIN, seed_peers


async def _peer_users_query(db: AsyncSession) -> list[User]:
    stmt = select(User).where(User.email.like(f"%{SEED_EMAIL_DOMAIN}"))
    return list((await db.execute(stmt)).scalars().all())


async def test_seed_peers_creates_exactly_90_users(test_session: AsyncSession):
    created = await seed_peers(test_session)
    assert created == PEER_COUNT == 90

    peers = await _peer_users_query(test_session)
    assert len(peers) == 90


async def test_seed_peers_all_opted_in(test_session: AsyncSession):
    await seed_peers(test_session)

    peers = await _peer_users_query(test_session)
    assert peers, "expected seed peers to be present"
    assert all(p.benchmark_opt_in is True for p in peers)


async def test_seed_peers_seniority_distribution(test_session: AsyncSession):
    await seed_peers(test_session)

    stmt = (
        select(User.seniority_level, func.count(User.id))
        .where(User.email.like(f"%{SEED_EMAIL_DOMAIN}"))
        .group_by(User.seniority_level)
    )
    rows = dict((await test_session.execute(stmt)).all())
    assert rows == {"junior": 30, "mid": 30, "senior": 30}


async def test_seed_peers_each_has_one_active_resume(test_session: AsyncSession):
    await seed_peers(test_session)

    peers = await _peer_users_query(test_session)
    assert len(peers) == 90

    for peer in peers:
        stmt = select(ParsedResume).where(
            ParsedResume.user_id == peer.id,
            ParsedResume.is_active.is_(True),
        )
        resumes = list((await test_session.execute(stmt)).scalars().all())
        assert len(resumes) == 1, (
            f"peer {peer.email} expected 1 active resume, got {len(resumes)}"
        )


async def test_seed_peers_is_idempotent(test_session: AsyncSession):
    first = await seed_peers(test_session)
    second = await seed_peers(test_session)

    assert first == 90
    assert second == 0

    peers = await _peer_users_query(test_session)
    assert len(peers) == 90

    # No duplicate resumes either.
    stmt = select(func.count(ParsedResume.id)).join(
        User, ParsedResume.user_id == User.id
    ).where(User.email.like(f"%{SEED_EMAIL_DOMAIN}"))
    total_resumes = (await test_session.execute(stmt)).scalar_one()
    assert total_resumes == 90
