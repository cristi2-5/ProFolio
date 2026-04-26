"""
Tests for the Benchmark Sanitizer utility (Phase 6 / Epic 5 / US 5.1).

Pure-function module — no DB, no mocking. Tests verify that:
    * Output never exposes user identifiers (GDPR guarantee).
    * Skills are normalised and deduped.
    * Years-of-experience falls back cleanly across resume shapes.
    * JD requirements extraction follows the tech extractor contract.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from app.utils.benchmark_sanitizer import (
    JobRequirements,
    SanitizedProfile,
    extract_job_requirements,
    sanitize_profile,
    skill_coverage_ratio,
    skill_gap,
)


class TestSanitizeProfile:
    """Behaviour of ``sanitize_profile``."""

    def test_no_user_identifiers_are_exposed(self) -> None:
        """Regression guard for the GDPR contract of this module."""
        field_names = {f.name for f in fields(SanitizedProfile)}
        forbidden = {"user_id", "email", "full_name", "name", "phone", "address"}
        assert forbidden.isdisjoint(field_names)

    def test_empty_resume_returns_empty_skills(self) -> None:
        profile = sanitize_profile(
            seniority_level="junior",
            niche=None,
            parsed_resume=None,
        )
        assert profile.skills == frozenset()
        assert profile.years_experience == 0.0
        assert profile.seniority_level == "junior"

    def test_skills_are_lowercased_and_deduped(self) -> None:
        resume = {
            "skills": ["Python", "python", "FastAPI"],
            "technologies": ["FastAPI", "Docker"],
        }
        profile = sanitize_profile(
            seniority_level="mid",
            niche="backend",
            parsed_resume=resume,
        )
        assert profile.skills == frozenset({"python", "fastapi", "docker"})

    def test_skills_can_come_as_dicts(self) -> None:
        resume = {"skills": [{"name": "React"}, {"skill": "TypeScript"}, "Tailwind"]}
        profile = sanitize_profile(
            seniority_level="junior", niche=None, parsed_resume=resume
        )
        assert profile.skills == frozenset({"react", "typescript", "tailwind"})

    def test_skills_string_fallback(self) -> None:
        resume = {"skills": "Python, JavaScript / TypeScript"}
        profile = sanitize_profile(
            seniority_level="junior", niche=None, parsed_resume=resume
        )
        assert profile.skills == frozenset({"python", "javascript", "typescript"})

    def test_explicit_years_is_preferred(self) -> None:
        resume = {
            "total_years_experience": 7.5,
            "experience": [{"duration": "2020-2023"}],  # ignored
        }
        profile = sanitize_profile(
            seniority_level="senior", niche="backend", parsed_resume=resume
        )
        assert profile.years_experience == 7.5

    def test_years_summed_from_role_dates(self) -> None:
        resume = {
            "experience": [
                {"start_date": "2018-01-01", "end_date": "2020-01-01"},  # ~2 yrs
                {"start_date": "2020-01-01", "end_date": "2022-01-01"},  # ~2 yrs
            ]
        }
        profile = sanitize_profile(
            seniority_level="mid", niche="backend", parsed_resume=resume
        )
        # Leap-year math gives ~4 years ± a few days.
        assert 3.9 <= profile.years_experience <= 4.1

    def test_present_marker_uses_today(self) -> None:
        resume = {"experience": [{"start_date": "2022-01-01", "end_date": "Present"}]}
        profile = sanitize_profile(
            seniority_level="mid", niche="frontend", parsed_resume=resume
        )
        assert profile.years_experience > 0

    def test_niche_preserved_for_mid_senior(self) -> None:
        profile = sanitize_profile(
            seniority_level="senior", niche="DevOps", parsed_resume={"skills": ["AWS"]}
        )
        assert profile.niche == "DevOps"

    def test_has_skill_is_case_insensitive(self) -> None:
        profile = sanitize_profile(
            seniority_level="junior", niche=None, parsed_resume={"skills": ["Python"]}
        )
        assert profile.has_skill("PYTHON")
        assert not profile.has_skill("Go")


class TestExtractJobRequirements:
    """Behaviour of ``extract_job_requirements``."""

    def test_empty_jd_returns_empty_requirements(self) -> None:
        req = extract_job_requirements("")
        assert req.required_skills == frozenset()
        assert req.min_years_experience == 0.0
        assert req.keywords == []

    def test_delegates_to_tech_extractor(self) -> None:
        req = extract_job_requirements(
            "We need a Python dev with FastAPI and PostgreSQL."
        )
        assert "python" in req.required_skills
        assert "fastapi" in req.required_skills
        assert "postgresql" in req.required_skills

    def test_parses_years_requirement(self) -> None:
        req = extract_job_requirements(
            "Senior Python engineer — 5+ years experience required."
        )
        assert req.min_years_experience == 5.0

    def test_parses_yrs_variant(self) -> None:
        req = extract_job_requirements("Looking for 3 yrs of backend experience.")
        assert req.min_years_experience == 3.0

    def test_keywords_mirror_required_skills(self) -> None:
        req = extract_job_requirements("React, TypeScript, Node.js stack.")
        # Same content via a different iteration order is acceptable; the
        # point is that keywords reflect the detected techs.
        assert {kw.lower() for kw in req.keywords} == req.required_skills


class TestSkillGapAndCoverage:
    """Primitives used by US 5.3."""

    @pytest.fixture
    def profile(self) -> SanitizedProfile:
        return sanitize_profile(
            seniority_level="mid",
            niche="backend",
            parsed_resume={"skills": ["Python", "FastAPI"]},
        )

    @pytest.fixture
    def requirements(self) -> JobRequirements:
        return JobRequirements(
            required_skills=frozenset({"python", "fastapi", "docker", "aws"}),
            min_years_experience=3.0,
            keywords=["Python", "FastAPI", "Docker", "AWS"],
        )

    def test_skill_gap_is_set_difference(
        self, profile: SanitizedProfile, requirements: JobRequirements
    ) -> None:
        assert skill_gap(profile, requirements) == frozenset({"docker", "aws"})

    def test_coverage_ratio(
        self, profile: SanitizedProfile, requirements: JobRequirements
    ) -> None:
        assert skill_coverage_ratio(profile, requirements) == pytest.approx(0.5)

    def test_coverage_empty_requirements_returns_zero(
        self, profile: SanitizedProfile
    ) -> None:
        empty = JobRequirements(
            required_skills=frozenset(), min_years_experience=0.0, keywords=[]
        )
        assert skill_coverage_ratio(profile, empty) == 0.0
