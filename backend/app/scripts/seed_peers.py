"""DEV-ONLY: Seed 90 synthetic peers for benchmarking.

The benchmarking feature requires at least 30 opted-in peers in the user's
seniority/niche bucket. In development databases this threshold is rarely met
naturally, so every benchmark request returns HTTP 422.

Running this script (idempotently) populates 90 deterministic synthetic peers
distributed evenly across seniority levels (30 junior + 30 mid + 30 senior) and
randomly across five niches (frontend / backend / fullstack / devops / data).
Each peer gets benchmark_opt_in=True and one active ParsedResume with a small
realistic skill set drawn from a per-niche bank.

Usage (inside the backend container):

    docker compose exec backend python -m app.scripts.seed_peers

Re-running the script is a no-op — peers are matched by email and skipped if
already present. Seed-only emails follow ``peer{NNN}@profolio.seed`` so they
can easily be filtered out of any production query
(``email NOT LIKE '%@profolio.seed'``).

This script must NEVER be run against a production database.
"""

from __future__ import annotations

import asyncio
import random
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.resume import ParsedResume
from app.models.user import User
from app.utils.security import hash_password

NICHE_SKILLS: Dict[str, List[str]] = {
    "frontend": [
        "React",
        "TypeScript",
        "JavaScript",
        "CSS",
        "HTML",
        "TailwindCSS",
        "Vite",
        "Next.js",
        "Redux",
        "Webpack",
    ],
    "backend": [
        "Python",
        "PostgreSQL",
        "Docker",
        "FastAPI",
        "Django",
        "Redis",
        "RabbitMQ",
        "REST APIs",
        "GraphQL",
        "SQLAlchemy",
    ],
    "fullstack": [
        "React",
        "TypeScript",
        "Node.js",
        "PostgreSQL",
        "Docker",
        "REST APIs",
        "Express",
        "MongoDB",
        "Tailwind",
    ],
    "devops": [
        "Docker",
        "Kubernetes",
        "Terraform",
        "AWS",
        "GCP",
        "CI/CD",
        "Linux",
        "Bash",
        "Helm",
        "Prometheus",
    ],
    "data": [
        "Python",
        "SQL",
        "PostgreSQL",
        "Pandas",
        "NumPy",
        "scikit-learn",
        "Apache Airflow",
        "Spark",
        "BigQuery",
        "DBT",
    ],
}

NICHES: List[str] = list(NICHE_SKILLS.keys())
SENIORITY_DISTRIBUTION: List[str] = (
    ["junior"] * 30 + ["mid"] * 30 + ["senior"] * 30
)
PEER_COUNT = len(SENIORITY_DISTRIBUTION)
SEED_PASSWORD = "PeerPass1!"
SEED_EMAIL_DOMAIN = "@profolio.seed"
RNG_SEED = 4242


async def seed_peers(db: AsyncSession) -> int:
    """Insert up to 90 synthetic peers; return count of NEW peers created.

    Idempotent: peers with an existing seed email are skipped. Re-runs return 0.
    """
    rng = random.Random(RNG_SEED)
    # Pre-generate a deterministic niche assignment per slot.
    niche_assignments = [rng.choice(NICHES) for _ in range(PEER_COUNT)]
    # Pre-generate skill samples per slot using the same seeded RNG so reruns
    # produce identical results.
    skill_assignments: List[List[str]] = []
    for niche in niche_assignments:
        bank = NICHE_SKILLS[niche]
        sample_size = rng.randint(5, 7)
        skill_assignments.append(rng.sample(bank, sample_size))

    # Hash the password once — bcrypt is intentionally slow.
    cached_password_hash = hash_password(SEED_PASSWORD)

    created = 0
    for i in range(PEER_COUNT):
        email = f"peer{i:03d}{SEED_EMAIL_DOMAIN}"
        seniority = SENIORITY_DISTRIBUTION[i]
        niche = niche_assignments[i]
        skills = skill_assignments[i]

        existing = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing is not None:
            continue

        user = User(
            email=email,
            password_hash=cached_password_hash,
            full_name=f"Seed Peer {i:03d}",
            seniority_level=seniority,
            niche=niche,
            benchmark_opt_in=True,
        )
        db.add(user)
        await db.flush()  # populate user.id

        parsed_data = {
            "skills": skills,
            "technologies": skills,
            "experience": [
                {
                    "title": f"{seniority.capitalize()} {niche} engineer",
                    "company": "Synthetic Labs",
                    "description": (
                        f"Worked across the {niche} stack using "
                        f"{', '.join(skills[:3])} and related tooling."
                    ),
                }
            ],
        }
        resume = ParsedResume(
            user_id=user.id,
            original_filename=f"peer_{i:03d}_resume.pdf",
            file_url=f"local://seed/peer_{i:03d}.pdf",
            parsed_data=parsed_data,
            is_active=True,
        )
        db.add(resume)
        created += 1

    await db.commit()
    return created


async def _main() -> None:
    async with async_session_factory() as db:
        created = await seed_peers(db)
    print(
        f"seed_peers: {created} new peer(s) inserted "
        f"(target total = {PEER_COUNT})."
    )


if __name__ == "__main__":
    asyncio.run(_main())
