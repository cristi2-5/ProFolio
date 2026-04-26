"""
Resume Service Tests — per-user upload quota enforcement.

Mocks the AsyncSession to keep these unit tests hermetic; integration
coverage of the full upload pipeline lives elsewhere.
"""

from __future__ import annotations

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException, UploadFile

from app.models.user import User
from app.services.resume_service import MAX_RESUMES_PER_USER, ResumeService


@pytest.fixture
def sample_user() -> User:
    u = Mock(spec=User)
    u.id = uuid.uuid4()
    u.email = "alex@example.com"
    return u


def _make_upload_file(name: str = "resume.pdf") -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(b"%PDF-1.4 fake"))


def _session_with_resume_count(count: int) -> AsyncMock:
    """Build an AsyncSession mock whose _count_user_resumes query returns `count`."""
    db = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = [Mock() for _ in range(count)]
    result = MagicMock()
    result.scalars.return_value = scalars
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_upload_under_quota_does_not_raise_quota_error(sample_user) -> None:
    """With fewer than MAX resumes, the quota gate must let the call proceed."""
    service = ResumeService.__new__(ResumeService)  # bypass __init__ (no FS / agent)
    service.cv_profiler = Mock()
    service.upload_dir = Mock()

    db = _session_with_resume_count(MAX_RESUMES_PER_USER - 1)

    # We don't need to run the rest of upload_and_parse — just assert the
    # quota guard doesn't fire. Patch the file-write step to short-circuit.
    with patch("builtins.open", side_effect=RuntimeError("stop-after-quota-check")):
        with pytest.raises(Exception) as exc_info:
            await service.upload_and_parse(db, sample_user, _make_upload_file())

    # Anything except an HTTPException(413) means we passed the quota gate.
    assert not (
        isinstance(exc_info.value, HTTPException) and exc_info.value.status_code == 413
    )


@pytest.mark.asyncio
async def test_upload_at_quota_raises_413(sample_user) -> None:
    """The MAX+1th upload must be rejected with HTTP 413."""
    service = ResumeService.__new__(ResumeService)
    service.cv_profiler = Mock()
    service.upload_dir = Mock()

    db = _session_with_resume_count(MAX_RESUMES_PER_USER)

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_and_parse(db, sample_user, _make_upload_file())

    assert exc_info.value.status_code == 413
    assert str(MAX_RESUMES_PER_USER) in exc_info.value.detail


@pytest.mark.asyncio
async def test_upload_well_over_quota_still_413(sample_user) -> None:
    """Quota check must use >= so legacy users above the limit can't sneak in."""
    service = ResumeService.__new__(ResumeService)
    service.cv_profiler = Mock()
    service.upload_dir = Mock()

    db = _session_with_resume_count(MAX_RESUMES_PER_USER + 10)

    with pytest.raises(HTTPException) as exc_info:
        await service.upload_and_parse(db, sample_user, _make_upload_file())

    assert exc_info.value.status_code == 413
