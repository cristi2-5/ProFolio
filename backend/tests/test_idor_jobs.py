"""IDOR regression tests — endpoints that take a job_id must reject cross-user access.

User A owns a UserJob. User B authenticates and tries to touch A's job via every
job-scoped endpoint. Each call must 403 *before* hitting the LLM service layer —
the service methods are patched to raise AssertionError if reached.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models.job import ScrapedJob, UserJob
from app.models.user import User
from app.utils.security import hash_password


async def _make_user(test_session, email: str, password: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=email.split("@")[0],
        seniority_level="mid",
        niche="Backend",
        benchmark_opt_in=False,
    )
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)
    return user


async def _login(client, email: str, password: str) -> str:
    resp = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_idor_other_user_job_endpoints_reject(client, test_session):
    # Two distinct users
    a_email = f"alice-{uuid.uuid4().hex[:8]}@example.com"
    b_email = f"bob-{uuid.uuid4().hex[:8]}@example.com"
    password = "IDORPassCode123!"

    user_a = await _make_user(test_session, a_email, password)
    await _make_user(test_session, b_email, password)

    # ScrapedJob + UserJob owned by A
    job = ScrapedJob(
        company_name="Acme Inc",
        job_title="Senior Backend Engineer",
        description="Build cool things",
        description_hash="h" * 64,
        location="Remote",
        source_platform="adzuna",
    )
    test_session.add(job)
    await test_session.flush()
    await test_session.refresh(job)

    user_job_a = UserJob(
        user_id=user_a.id,
        job_id=job.id,
        match_score=80,
        status="new",
    )
    test_session.add(user_job_a)
    await test_session.commit()

    # Login as B
    b_token = await _login(client, b_email, password)
    headers = {"Authorization": f"Bearer {b_token}"}

    job_id = str(job.id)
    interview_payload = {
        "include_user_background": True,
        "technical_count": 3,
        "behavioral_count": 2,
    }

    # Patch service methods to BLOW UP if reached — should never be called when 403'd
    sentinel = AssertionError("auth check should reject before reaching LLM")

    with patch(
        "app.services.cv_optimizer_service.CVOptimizerService.optimize_cv_for_job",
        new=AsyncMock(side_effect=sentinel),
    ), patch(
        "app.services.cv_optimizer_service.CVOptimizerService.generate_cover_letter",
        new=AsyncMock(side_effect=sentinel),
    ), patch(
        "app.services.interview_coach_service.InterviewCoachService.generate_interview_prep_materials",
        new=AsyncMock(side_effect=sentinel),
    ):
        # POST /api/cv-optimizer/optimize
        r = await client.post(
            "/api/cv-optimizer/optimize",
            headers=headers,
            json={"job_id": job_id},
        )
        assert r.status_code == 403, r.text

        # POST /api/cv-optimizer/cover-letter
        r = await client.post(
            "/api/cv-optimizer/cover-letter",
            headers=headers,
            json={"job_id": job_id},
        )
        assert r.status_code == 403, r.text

        # GET /api/cv-optimizer/export/cover-letter/{job_id}
        r = await client.get(
            f"/api/cv-optimizer/export/cover-letter/{job_id}",
            headers=headers,
        )
        assert r.status_code == 403, r.text

        # POST /api/jobs/{job_id}/generate-interview-prep
        r = await client.post(
            f"/api/jobs/{job_id}/generate-interview-prep",
            headers=headers,
            json=interview_payload,
        )
        assert r.status_code == 403, r.text

        # POST /api/jobs/{job_id}/generate-interview-prep-async
        r = await client.post(
            f"/api/jobs/{job_id}/generate-interview-prep-async",
            headers=headers,
            json=interview_payload,
        )
        assert r.status_code == 403, r.text

        # GET /api/jobs/{job_id}/interview-prep
        r = await client.get(
            f"/api/jobs/{job_id}/interview-prep", headers=headers
        )
        assert r.status_code == 403, r.text

        # PATCH /api/jobs/{job_id}/interview-prep
        r = await client.patch(
            f"/api/jobs/{job_id}/interview-prep",
            headers=headers,
            json={"user_notes": "trying to peek"},
        )
        assert r.status_code == 403, r.text

        # POST /api/jobs/{job_id}/calculate-benchmark
        r = await client.post(
            f"/api/jobs/{job_id}/calculate-benchmark", headers=headers
        )
        assert r.status_code == 403, r.text

        # GET /api/benchmarks/job/{job_id}
        r = await client.get(f"/api/benchmarks/job/{job_id}", headers=headers)
        assert r.status_code == 403, r.text
