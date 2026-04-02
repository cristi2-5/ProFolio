"""
Auto-Apply Backend — Database Connection & Session Management.

Uses SQLAlchemy 2.0 async engine with asyncpg driver for PostgreSQL.
Provides a dependency-injectable async session for FastAPI routes.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Async engine — connection pool managed by SQLAlchemy
engine = create_async_engine(
    settings.database_url,
    echo=(settings.environment == "development"),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Session factory — produces AsyncSession instances
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    All models inherit from this to share the same metadata
    and be discovered by Alembic for auto-generating migrations.
    """

    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session.

    Yields:
        AsyncSession: An active database session. Automatically
        closed when the request completes.

    Example:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
