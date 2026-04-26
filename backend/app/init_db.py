#!/usr/bin/env python3
"""
Database Initialization Script.

Creates all database tables from SQLAlchemy models.
Run this when setting up a new environment.
"""

import asyncio

from app.database import Base, engine
from app.models.benchmark import BenchmarkScore
from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume

# Import all models to ensure they're registered with Base.metadata
from app.models.user import JobPreference, User


async def init_db():
    """Create all database tables."""
    print("Creating database tables...")

    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Database tables created successfully!")


if __name__ == "__main__":
    asyncio.run(init_db())
