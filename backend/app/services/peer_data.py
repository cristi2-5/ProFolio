"""
Shared peer / resume loaders for the benchmarking subsystem.

Both ``BenchmarkService`` and ``RecommendationsService`` need to load:

    * the requesting user's active parsed resume
    * sanitized profiles of every opt-in peer at the same seniority
      (and niche, for mid/senior)

Previously each service carried its own copy of the SQL — a maintenance
hazard given the GDPR consent rules the peer query has to honour. This
module owns those two queries as a single source of truth so adding a
new filter (e.g. tightening niche matching) only touches one place.

The peer query routes every row through ``sanitize_profile`` before
returning, so callers never see PII.
"""

from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import ParsedResume
from app.models.user import User
from app.utils.benchmark_sanitizer import SanitizedProfile, sanitize_profile

MID_SENIOR_LEVELS = frozenset({"mid", "senior"})


async def load_active_resume(user: User, db: AsyncSession) -> Optional[ParsedResume]:
    """Return the user's active ``ParsedResume`` row, or ``None`` if missing."""
    stmt = select(ParsedResume).where(
        ParsedResume.user_id == user.id,
        ParsedResume.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def load_peer_profiles(
    *,
    user: User,
    db: AsyncSession,
) -> List[SanitizedProfile]:
    """Return sanitized profiles of every eligible peer.

    Peer eligibility:
        * ``benchmark_opt_in`` is True (GDPR consent).
        * Same ``seniority_level`` as the requesting user.
        * Same ``niche`` — mid/senior only.
        * Has an active parsed resume.
        * Is not the requesting user.
    """
    conditions: List[Any] = [
        User.benchmark_opt_in.is_(True),
        User.id != user.id,
        User.seniority_level == user.seniority_level,
        ParsedResume.is_active.is_(True),
    ]
    if user.seniority_level in MID_SENIOR_LEVELS and user.niche:
        conditions.append(User.niche == user.niche)

    stmt = (
        select(User.seniority_level, User.niche, ParsedResume.parsed_data)
        .join(ParsedResume, ParsedResume.user_id == User.id)
        .where(and_(*conditions))
    )
    result = await db.execute(stmt)
    return [
        sanitize_profile(
            seniority_level=level,
            niche=niche,
            parsed_resume=parsed_data,
        )
        for level, niche, parsed_data in result.all()
    ]
