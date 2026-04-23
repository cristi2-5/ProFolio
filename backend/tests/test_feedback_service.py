"""
Tests for the Feedback Service (Phase 7 — beta launch).

The service is thin, so the tests focus on:
    * Correct ORM row construction on create.
    * Rollback on DB error.
    * Aggregate-stats shape under typical data.

Real DB tests live in the integration suite (Postgres-required). Here
we mock the AsyncSession to keep unit tests hermetic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.models.feedback import Feedback
from app.models.user import User
from app.schemas.feedback import FeedbackCreateRequest
from app.services.feedback_service import FeedbackService


@pytest.fixture
def service() -> FeedbackService:
    return FeedbackService()


@pytest.fixture
def sample_user() -> User:
    u = Mock(spec=User)
    u.id = uuid.uuid4()
    u.email = "test@example.com"
    return u


class TestCreate:
    @pytest.mark.asyncio
    async def test_happy_path_persists_row(self, service, sample_user) -> None:
        db = AsyncMock()
        db.add = Mock()

        async def _refresh(row):
            row.id = uuid.uuid4()
            row.created_at = datetime.now(timezone.utc)

        db.refresh.side_effect = _refresh

        payload = FeedbackCreateRequest(
            content_type="interview_prep",
            content_id="job-123",
            rating=5,
            comment="Very useful",
        )
        row = await service.create(user=sample_user, payload=payload, db=db)

        assert isinstance(row, Feedback)
        assert row.user_id == sample_user.id
        assert row.content_type == "interview_prep"
        assert row.rating == 5
        assert row.comment == "Very useful"
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_error_rolls_back(self, service, sample_user) -> None:
        db = AsyncMock()
        db.add = Mock()
        db.commit.side_effect = RuntimeError("pg died")

        payload = FeedbackCreateRequest(
            content_type="optimized_cv", rating=4, comment=None
        )

        with pytest.raises(RuntimeError, match="pg died"):
            await service.create(user=sample_user, payload=payload, db=db)
        db.rollback.assert_awaited_once()


class TestListForUser:
    @pytest.mark.asyncio
    async def test_returns_scalars_in_order(self, service, sample_user) -> None:
        db = AsyncMock()
        rows = [Mock(spec=Feedback) for _ in range(3)]
        scalars = MagicMock()
        scalars.all.return_value = rows
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars
        db.execute.return_value = execute_result

        result = await service.list_for_user(user=sample_user, db=db, limit=10)
        assert result == rows
        db.execute.assert_awaited_once()


class TestAggregateStats:
    @pytest.mark.asyncio
    async def test_aggregation_returns_typed_entries(self, service) -> None:
        db = AsyncMock()
        row_a = Mock(
            content_type="interview_prep", count=10, average=4.5, low_rating_count=1
        )
        row_b = Mock(
            content_type="optimized_cv", count=5, average=3.2, low_rating_count=2
        )
        execute_result = MagicMock()
        execute_result.all.return_value = [row_a, row_b]
        db.execute.return_value = execute_result

        stats = await service.aggregate_stats(db=db)
        assert stats == [
            {
                "content_type": "interview_prep",
                "count": 10,
                "average_rating": 4.5,
                "low_rating_count": 1,
            },
            {
                "content_type": "optimized_cv",
                "count": 5,
                "average_rating": 3.2,
                "low_rating_count": 2,
            },
        ]

    @pytest.mark.asyncio
    async def test_missing_average_is_zero(self, service) -> None:
        db = AsyncMock()
        row = Mock(content_type="benchmark", count=0, average=None, low_rating_count=0)
        execute_result = MagicMock()
        execute_result.all.return_value = [row]
        db.execute.return_value = execute_result

        stats = await service.aggregate_stats(db=db)
        assert stats == [
            {
                "content_type": "benchmark",
                "count": 0,
                "average_rating": 0.0,
                "low_rating_count": 0,
            }
        ]
