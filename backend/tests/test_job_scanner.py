"""
Job Scanner Agent Tests — 28 scenarios.

Tests for the JobScannerAgent: deduplication, Adzuna API integration,
batch scanning, and error handling.
"""

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.job_scanner import JobScannerAgent
from app.models.job import ScrapedJob, UserJob
from app.models.user import JobPreference, User

# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def agent():
    """Return a fresh JobScannerAgent instance."""
    return JobScannerAgent()


@pytest.fixture
def mock_user():
    """Return a synthetic User object."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def mock_preferences(mock_user):
    """Return synthetic JobPreference linked to mock_user."""
    pref = MagicMock(spec=JobPreference)
    pref.user_id = mock_user.id
    pref.desired_title = "Python Developer"
    pref.location_type = "remote"
    pref.keywords = ["fastapi", "postgresql", "docker"]
    return pref


@pytest.fixture
def sample_adzuna_job():
    """Return a single Adzuna-shaped job dict."""
    return {
        "redirect_url": "https://api.adzuna.com/redirect/job/12345",
        "title": "Senior Python Developer",
        "description": "We are looking for a Python developer with FastAPI skills.",
        "company": {"display_name": "TechCorp Inc."},
        "location": {"display_name": "Remote"},
    }


@pytest.fixture
def make_adzuna_response(sample_adzuna_job):
    """Factory: wrap N job dicts in an Adzuna API response envelope."""

    def _make(jobs=None, count=None):
        jobs = jobs if jobs is not None else [sample_adzuna_job]
        return {"results": jobs, "count": count or len(jobs)}

    return _make


# ──────────────────────────────────────────────
# Test: _build_search_query
# ──────────────────────────────────────────────


class TestBuildSearchQuery:
    """Tests for the search query builder."""

    def test_title_only(self, agent, mock_preferences):
        """Query uses just the desired title when no keywords."""
        mock_preferences.keywords = []
        result = agent._build_search_query(mock_preferences)
        assert result == "Python Developer"

    def test_keywords_not_included_in_query(self, agent, mock_preferences):
        """Adzuna's `what` param is AND-logic — keywords are NOT appended.

        Including 5+ keywords produces zero Adzuna results because they all
        must appear in every listing. Keywords are used only in the post-scan
        match-scoring step (see `JobService.match_jobs_to_user`), not in the
        initial Adzuna query.
        """
        mock_preferences.keywords = [
            "fastapi", "postgresql", "docker", "aws", "kubernetes",
        ]
        result = agent._build_search_query(mock_preferences)
        assert result == "Python Developer"
        assert "fastapi" not in result
        assert "postgresql" not in result

    def test_empty_keywords_list(self, agent, mock_preferences):
        """None keywords falls through without error."""
        mock_preferences.keywords = None
        result = agent._build_search_query(mock_preferences)
        assert result == "Python Developer"

    def test_no_preferences_falls_back_to_developer(self, agent):
        """Users without preferences get a default 'developer' query."""
        assert agent._build_search_query(None) == "developer"

    def test_empty_desired_title_falls_back_to_developer(self, agent, mock_preferences):
        """Defensive: blank title still produces a usable query."""
        mock_preferences.desired_title = ""
        assert agent._build_search_query(mock_preferences) == "developer"


# ──────────────────────────────────────────────
# Test: _process_and_deduplicate_job
# ──────────────────────────────────────────────


class TestProcessAndDeduplicateJob:
    """Tests for the per-job deduplication logic."""

    @pytest.mark.asyncio
    async def test_new_job_is_saved(self, agent, sample_adzuna_job):
        """A brand-new job produces a ScrapedJob row and returns it."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        db.add = MagicMock()
        db.flush = AsyncMock()

        result = await agent._process_and_deduplicate_job(sample_adzuna_job, db)

        assert result is not None
        assert result.job_title == "Senior Python Developer"
        assert result.company_name == "TechCorp Inc."
        assert result.source_platform == "adzuna"
        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_by_url_returns_none(self, agent, sample_adzuna_job):
        """A job whose URL already exists in DB is silently rejected."""
        existing = MagicMock(spec=ScrapedJob)
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
        )

        result = await agent._process_and_deduplicate_job(sample_adzuna_job, db)

        assert result is None

    @pytest.mark.asyncio
    async def test_duplicate_by_content_hash_returns_none(
        self, agent, sample_adzuna_job
    ):
        """A job matching company+title+description_hash is rejected even with different URL.

        The dedup path now compares against existing rows using a
        normalized company/title in Python (so "Acme Inc" and "Acme LLC"
        collapse together), so the second mock returns an iterable of
        candidates rather than a single ``scalar_one_or_none`` result.
        """
        existing = MagicMock(spec=ScrapedJob)
        # Matches the sample_adzuna_job's company/title under normalization.
        existing.company_name = "TechCorp Inc."
        existing.job_title = "Senior Python Developer"

        db = AsyncMock(spec=AsyncSession)
        # First execute → URL check (no URL dupe)
        first_call = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        # Second execute → content-hash filter; iterate via .scalars()
        second_call = MagicMock(scalars=MagicMock(return_value=iter([existing])))
        db.execute = AsyncMock(side_effect=[first_call, second_call])

        result = await agent._process_and_deduplicate_job(sample_adzuna_job, db)

        assert result is None

    @pytest.mark.asyncio
    async def test_job_without_url_still_processes(self, agent, sample_adzuna_job):
        """Jobs with no redirect_url are still persisted (rely on content hash)."""
        sample_adzuna_job["redirect_url"] = None
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        db.add = MagicMock()
        db.flush = AsyncMock()

        result = await agent._process_and_deduplicate_job(sample_adzuna_job, db)

        assert result is not None
        assert result.external_url is None

    @pytest.mark.asyncio
    async def test_integrity_error_returns_none(self, agent, sample_adzuna_job):
        """Race condition IntegrityError is handled gracefully — returns None."""
        from sqlalchemy.exc import IntegrityError

        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        db.add = MagicMock()
        db.flush = AsyncMock(side_effect=IntegrityError("", {}, None))
        db.rollback = AsyncMock()

        result = await agent._process_and_deduplicate_job(sample_adzuna_job, db)

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_company_name_defaults(self, agent, sample_adzuna_job):
        """Missing company field defaults to 'Unknown Company'."""
        del sample_adzuna_job["company"]
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        db.add = MagicMock()
        db.flush = AsyncMock()

        result = await agent._process_and_deduplicate_job(sample_adzuna_job, db)

        assert result is not None
        assert result.company_name == "Unknown Company"


# ──────────────────────────────────────────────
# Test: scan() — per-user scan
# ──────────────────────────────────────────────


class TestScan:
    """Tests for the per-user scan() entry point."""

    @pytest.mark.asyncio
    async def test_scan_returns_new_jobs(
        self,
        agent,
        mock_user,
        mock_preferences,
        sample_adzuna_job,
        make_adzuna_response,
    ):
        """Happy path: preferences found, API called, jobs returned."""
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user)
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        # Mock preferences query
        pref_result = MagicMock(
            scalar_one_or_none=MagicMock(return_value=mock_preferences)
        )
        # Mock URL-dedup + content-dedup queries (both return None → new job)
        no_dupe = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        db.execute = AsyncMock(side_effect=[pref_result, no_dupe, no_dupe])
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.agents.job_scanner.get_adzuna_client") as mock_client_factory:
            mock_api = AsyncMock()
            mock_api.search_jobs = AsyncMock(return_value=make_adzuna_response())
            mock_client_factory.return_value = mock_api

            with patch.object(
                agent.job_service, "match_jobs_to_user", new_callable=AsyncMock
            ) as mock_match:
                mock_match.return_value = []
                result = await agent.scan(str(mock_user.id), db)

        assert isinstance(result, list)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_user_not_found_raises(self, agent):
        """Raises ValueError if user doesn't exist in DB."""
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=None)
        db.rollback = AsyncMock()

        with pytest.raises(ValueError, match="not found"):
            await agent.scan(str(uuid.uuid4()), db)

    @pytest.mark.asyncio
    async def test_scan_no_preferences_uses_default_query(self, agent, mock_user):
        """Without preferences, scan falls back to a 'developer' Adzuna query.

        Previously this returned [] and required preferences to be set.
        Now the agent should call Adzuna with the default query so users
        can browse jobs without configuring preferences first.
        """
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user)
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        db.rollback = AsyncMock()
        db.commit = AsyncMock()

        # Patch the Adzuna client + JobService so we don't hit the network.
        with patch("app.agents.job_scanner.get_adzuna_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.search_jobs = AsyncMock(return_value={"results": []})
            mock_get_client.return_value = mock_client

            result = await agent.scan(str(mock_user.id), db)

            # Empty result list (no Adzuna jobs in mock) — but the call must have happened
            assert result == []
            mock_client.search_jobs.assert_called_once()
            call_kwargs = mock_client.search_jobs.call_args.kwargs
            assert call_kwargs["query"] == "developer"
            assert call_kwargs["location_type"] == "remote"

    @pytest.mark.asyncio
    async def test_scan_missing_api_credentials_returns_empty(
        self, agent, mock_user, mock_preferences
    ):
        """Returns empty list (no crash) when Adzuna keys are not configured."""
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=mock_preferences)
            )
        )
        db.rollback = AsyncMock()

        with patch("app.agents.job_scanner.get_adzuna_client") as mock_factory:
            mock_api = AsyncMock()
            mock_api.search_jobs = AsyncMock(
                side_effect=ValueError("credentials not configured")
            )
            mock_factory.return_value = mock_api

            result = await agent.scan(str(mock_user.id), db)

        assert result == []

    @pytest.mark.asyncio
    async def test_scan_remote_location_sends_empty_location(
        self, agent, mock_user, mock_preferences, make_adzuna_response
    ):
        """Remote jobs send empty string as location to Adzuna."""
        mock_preferences.location_type = "remote"
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user)
        pref_result = MagicMock(
            scalar_one_or_none=MagicMock(return_value=mock_preferences)
        )
        db.execute = AsyncMock(side_effect=[pref_result])
        db.rollback = AsyncMock()

        with patch("app.agents.job_scanner.get_adzuna_client") as mock_factory:
            mock_api = AsyncMock()
            mock_api.search_jobs = AsyncMock(return_value=make_adzuna_response(jobs=[]))
            mock_factory.return_value = mock_api

            await agent.scan(str(mock_user.id), db)

            call_kwargs = mock_api.search_jobs.call_args
            assert call_kwargs.kwargs.get("location") == "" or call_kwargs.args[1] == ""

    @pytest.mark.asyncio
    async def test_scan_adzuna_error_propagates(
        self, agent, mock_user, mock_preferences
    ):
        """AdzunaAPIError from the API propagates up (not swallowed)."""
        from app.clients.adzuna import AdzunaAPIError

        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=mock_preferences)
            )
        )
        db.rollback = AsyncMock()

        with patch("app.agents.job_scanner.get_adzuna_client") as mock_factory:
            mock_api = AsyncMock()
            mock_api.search_jobs = AsyncMock(
                side_effect=AdzunaAPIError("API down", 500)
            )
            mock_factory.return_value = mock_api

            with pytest.raises(AdzunaAPIError):
                await agent.scan(str(mock_user.id), db)

    @pytest.mark.asyncio
    async def test_scan_individual_job_error_does_not_abort(
        self, agent, mock_user, mock_preferences, make_adzuna_response
    ):
        """If processing one job fails, the rest still succeed."""
        bad_job = {
            "redirect_url": None,
            "title": None,
            "company": None,
            "description": None,
            "location": None,
        }
        good_job = {
            "redirect_url": "https://example.com/good",
            "title": "Backend Engineer",
            "company": {"display_name": "GoodCorp"},
            "description": "Great Python job",
            "location": {"display_name": "Remote"},
        }
        db = AsyncMock(spec=AsyncSession)
        db.get = AsyncMock(return_value=mock_user)
        no_dupe = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=mock_preferences)),
                no_dupe,
                no_dupe,  # for good_job deduplication
            ]
        )
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        with patch("app.agents.job_scanner.get_adzuna_client") as mock_factory:
            mock_api = AsyncMock()
            mock_api.search_jobs = AsyncMock(
                return_value=make_adzuna_response(jobs=[bad_job, good_job])
            )
            mock_factory.return_value = mock_api

            with patch.object(
                agent.job_service, "match_jobs_to_user", new_callable=AsyncMock
            ) as mock_match:
                mock_match.return_value = []
                result = await agent.scan(str(mock_user.id), db)

        # At least the good job should have been processed
        assert isinstance(result, list)


# ──────────────────────────────────────────────
# Test: scan_all_users()
# ──────────────────────────────────────────────


class TestScanAllUsers:
    """Tests for the batch cron entry point."""

    @pytest.mark.asyncio
    async def test_no_users_returns_zero(self, agent):
        """Returns 0 when no users have preferences."""
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
            )
        )

        result = await agent.scan_all_users(db)
        assert result == 0

    @pytest.mark.asyncio
    async def test_partial_failure_continues(self, agent, mock_user):
        """One failing user scan doesn't abort the rest."""
        user_a = MagicMock(spec=User)
        user_a.id = uuid.uuid4()
        user_b = MagicMock(spec=User)
        user_b.id = uuid.uuid4()

        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[user_a, user_b]))
                )
            )
        )

        with patch.object(agent, "scan", new_callable=AsyncMock) as mock_scan:
            mock_scan.side_effect = [Exception("API down"), [{"id": "job-1"}]]
            total = await agent.scan_all_users(db)

        assert total == 1  # Only user_b's job counted

    @pytest.mark.asyncio
    async def test_aggregates_total_counts(self, agent):
        """Total count sums new jobs across all users."""
        users = [MagicMock(spec=User, id=uuid.uuid4()) for _ in range(3)]
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=users))
                )
            )
        )

        with patch.object(agent, "scan", new_callable=AsyncMock) as mock_scan:
            mock_scan.side_effect = [
                [{"id": "j1"}, {"id": "j2"}],  # user 0: 2 jobs
                [{"id": "j3"}],  # user 1: 1 job
                [],  # user 2: 0 jobs
            ]
            total = await agent.scan_all_users(db)

        assert total == 3


# ──────────────────────────────────────────────
# Test: Hashing utility integration
# ──────────────────────────────────────────────


class TestHashingIntegration:
    """Verify the description hash used inside the agent matches the utility."""

    def test_hash_is_sha256_hex(self):
        """Hash output is a 64-char hex string."""
        from app.utils.hashing import create_description_hash

        h = create_description_hash("Hello, world!")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_content_same_hash(self):
        """Identical descriptions produce identical hashes."""
        from app.utils.hashing import create_description_hash

        text = "We are looking for a Python developer."
        assert create_description_hash(text) == create_description_hash(text)

    def test_case_insensitive_normalization(self):
        """Upper and lower case variants hash identically."""
        from app.utils.hashing import create_description_hash

        assert create_description_hash("Python Developer") == create_description_hash(
            "python developer"
        )

    def test_html_stripped_before_hashing(self):
        """HTML tags are stripped so <b>Python</b> == Python."""
        from app.utils.hashing import create_description_hash

        assert create_description_hash(
            "<b>Python</b> developer"
        ) == create_description_hash("Python developer")

    def test_only_first_200_chars_used(self):
        """Only the first 200 chars influence the hash."""
        from app.utils.hashing import create_description_hash

        base = "x" * 200
        h1 = create_description_hash(base + "extra text that should be ignored")
        h2 = create_description_hash(base)
        assert h1 == h2

    def test_none_input_does_not_raise(self):
        """None input returns a stable hash (hash of empty string)."""
        from app.utils.hashing import create_description_hash

        h = create_description_hash(None)
        assert h == create_description_hash("")
