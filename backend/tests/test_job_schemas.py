"""
Jobs Router & Schema Tests.

Tests for:
- GET /api/jobs/{user_job_id}
- UserJobResponse schema flattening
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.schemas.job import UserJobResponse


class MockJob:
    """Mock ScrapedJob for testing schema conversion."""

    def __init__(self):
        self.id = uuid.uuid4()
        self.job_title = "Lead Architecture"
        self.company_name = "CloudScale"
        self.location = "San Francisco, CA"
        self.external_url = "https://cloudscale.com/jobs/1"
        self.description = "Design global systems."
        self.salary_min = 150000
        self.salary_max = 250000
        self.job_type = "full_time"


class MockUserJob:
    """Mock UserJob for testing schema conversion."""

    def __init__(self, job):
        self.id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.job_id = job.id
        self.match_score = 95
        self.status = "new"
        self.optimized_cv = None
        self.cover_letter = None
        self.interview_prep = None
        self.applied_at = None
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.job = job


def test_user_job_response_flattens_nested_job():
    """Verify the UserJobResponse schema flattens ScrapedJob fields at the top level."""
    m_job = MockJob()
    m_user_job = MockUserJob(m_job)

    # Convert to schema
    response = UserJobResponse.model_validate(m_user_job)

    # Check top-level flattened fields
    assert response.job_title == "Lead Architecture"
    assert response.company_name == "CloudScale"
    assert response.location == "San Francisco, CA"
    assert response.external_url == "https://cloudscale.com/jobs/1"
    assert response.description == "Design global systems."
    assert response.salary_min == 150000
    assert response.salary_max == 250000
    assert response.job_type == "full_time"

    # Verify ID is the UserJob ID, not the ScrapedJob ID
    assert response.id == m_user_job.id


def test_user_job_response_handles_missing_job_gracefully():
    """Verify the UserJobResponse doesn't crash if the inner job is None."""

    class FakeUserJob:
        id = uuid.uuid4()
        user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        match_score = 50
        status = "new"
        optimized_cv = None
        cover_letter = None
        interview_prep = None
        applied_at = None
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)
        job = None  # Missing relationship

    response = UserJobResponse.model_validate(FakeUserJob())
    assert response.job_title == ""
    assert response.company_name == ""
    assert response.location is None
