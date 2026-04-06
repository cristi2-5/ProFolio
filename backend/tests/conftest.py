"""
Pytest Configuration and Shared Fixtures.

Provides test client fixture and test database setup for isolated testing.
Each test runs in a transaction that rolls back automatically.
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.database import Base, get_db
from app.main import app

# Test database configuration
settings = get_settings()
TEST_DATABASE_URL = settings.database_url.replace(
    "/autoapply_db", "/autoapply_test_db"
)


@pytest.fixture(scope="session")
def event_loop_policy():
    """Create an event loop for the test session.

    Required for pytest-asyncio to work with session-scoped fixtures.
    """
    policy = asyncio.get_event_loop_policy()
    
    return policy
    


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine.

    Creates a fresh test database at session start and drops it at session end.
    Ensures all connections are closed before dropping.
    """
    # Create engine for postgres database (to create/drop test DB)
    admin_url = settings.database_url.replace("/autoapply_db", "/postgres")
    admin_engine = create_async_engine(
        admin_url,
        isolation_level="AUTOCOMMIT",
    )

    # Force disconnect all sessions and recreate test database
    async with admin_engine.connect() as conn:
        await conn.execute(text("DROP DATABASE IF EXISTS autoapply_test_db WITH (FORCE)"))
        await conn.execute(text("CREATE DATABASE autoapply_test_db"))

    await admin_engine.dispose()

    # Create engine for test database
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables (ensure clean start)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Final Cleanup: ensure all connections are disposed
    await engine.dispose()

    # Final drop (optional but cleaner)
    admin_engine_cleanup = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine_cleanup.connect() as conn:
        await conn.execute(text("DROP DATABASE IF EXISTS autoapply_test_db WITH (FORCE)"))
    await admin_engine_cleanup.dispose()


@pytest_asyncio.fixture
async def test_session(
    test_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session with transaction rollback.

    Each test runs in a transaction that automatically rolls back,
    ensuring test isolation without database cleanup overhead.
    """
    # Create session factory
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        async with session.begin_nested():
            yield session
            # Transaction automatically rolls back after yield


@pytest_asyncio.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with test database.

    Uses httpx ASGITransport to call FastAPI directly
    without needing a live server instance. Overrides the database
    dependency with the test session.

    Yields:
        AsyncClient: Configured test client scoped to the test function.
    """

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clean up dependency override
    app.dependency_overrides.clear()
