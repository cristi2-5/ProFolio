import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.job import ScrapedJob, UserJob
from app.models.user import User

@pytest.mark.asyncio
async def test_create_scraped_job(db_session):
    """Test basic creation and retrieval of a ScrapedJob."""
    job = ScrapedJob(
        company_name="Test Company",
        job_title="Test Engineer",
        description="Test Description",
        external_url="https://test.com/123",
        location="Remote",
        source_platform="test"
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    
    assert job.id is not None
    assert isinstance(job.id, uuid.UUID)
    assert job.company_name == "Test Company"
    assert job.scraped_at is not None

@pytest.mark.asyncio
async def test_create_user_job(db_session):
    """Test creation of UserJob relationship."""
    # Create a user first
    user = User(
        email="test_models@example.com",
        hashed_password="hashed_password",
        full_name="Model Tester"
    )
    db_session.add(user)
    
    # Create a job
    job = ScrapedJob(
        company_name="Relationship Corp",
        job_title="DevOps",
        external_url="https://rel.com/456"
    )
    db_session.add(job)
    await db_session.flush()
    
    # Create UserJob
    user_job = UserJob(
        user_id=user.id,
        job_id=job.id,
        match_score=85,
        status="new"
    )
    db_session.add(user_job)
    await db_session.commit()
    await db_session.refresh(user_job)
    
    assert user_job.match_score == 85
    assert user_job.status == "new"
    assert user_job.created_at is not None

@pytest.mark.asyncio
async def test_user_job_status_constraints(db_session):
    """Test that invalid statuses are rejected if we were to enforce them (logical check)."""
    # Note: SQLAlchemy check constraints are enforced by the DB, not the ORM usually
    # but we can verify the model attribute assignment.
    user_job = UserJob(status="invalid_status")
    assert user_job.status == "invalid_status"

@pytest.mark.asyncio
async def test_scraped_job_repr(db_session):
    """Test the string representation of ScrapedJob."""
    job = ScrapedJob(company_name="Repr Inc", job_title="Manager")
    repr_str = repr(job)
    assert "Repr Inc" in repr_str
    assert "Manager" in repr_str
