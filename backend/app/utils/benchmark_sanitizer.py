"""
Benchmark Sanitizer — GDPR-compliant peer data extraction.

Strips everything except the four fields that are load-bearing for
competitive benchmarking:

    * seniority_level
    * niche
    * years_experience
    * skills (lowercased, deduplicated)

The output is explicitly decoupled from the user's identity — no user_id,
email, name, or other PII is ever present in the ``SanitizedProfile``
dataclass. Callers must go through this module when reading peer data; the
benchmark service relies on that invariant for its GDPR claims.

Pure functions only — no DB access, no side effects, fully testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.utils.tech_extractor import extract_technologies


@dataclass(frozen=True)
class SanitizedProfile:
    """Peer profile stripped of PII and personal identifiers.

    Intentionally missing: user_id, email, name, phone, address, company
    names, role titles, education institutions, free-text bullet points.
    """

    seniority_level: Optional[str]
    niche: Optional[str]
    years_experience: float
    skills: frozenset[str]

    def has_skill(self, skill: str) -> bool:
        """Case-insensitive skill-membership check."""
        return skill.lower() in self.skills


@dataclass(frozen=True)
class JobRequirements:
    """Sanitized view of what a Job Description is asking for.

    Uses the existing deterministic tech extractor so JD parsing is shared
    with the Interview Coach and cannot drift between features.
    """

    required_skills: frozenset[str]
    min_years_experience: float = 0.0
    keywords: List[str] = field(default_factory=list)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def sanitize_profile(
    *,
    seniority_level: Optional[str],
    niche: Optional[str],
    parsed_resume: Optional[Dict[str, Any]],
) -> SanitizedProfile:
    """Build a ``SanitizedProfile`` from raw user + parsed-resume data.

    Args:
        seniority_level: User's self-reported seniority (from ``users``).
        niche: User's technical niche (from ``users``). Unused for
            intern/junior but required by the spec for mid/senior grouping.
        parsed_resume: The ``ParsedResume.parsed_data`` JSONB payload.
            Everything outside the expected skill/experience fields is
            discarded.

    Returns:
        A ``SanitizedProfile`` safe to use in aggregate calculations.
    """
    skills = _extract_skills(parsed_resume)
    years = _compute_years_experience(parsed_resume)
    return SanitizedProfile(
        seniority_level=(seniority_level or None),
        niche=(niche or None) if niche else None,
        years_experience=years,
        skills=frozenset(skills),
    )


def extract_job_requirements(job_description: str) -> JobRequirements:
    """Turn a raw JD string into a ``JobRequirements`` payload.

    Delegates tech extraction to ``tech_extractor`` so this stays aligned
    with the Interview Coach's understanding of which technologies the JD
    actually mentions.
    """
    if not job_description:
        return JobRequirements(
            required_skills=frozenset(), min_years_experience=0.0, keywords=[]
        )

    techs = extract_technologies(job_description, max_results=30)
    skills = frozenset(t.name.lower() for t in techs)
    years = _parse_years_requirement(job_description)
    keywords = [t.name for t in techs]
    return JobRequirements(
        required_skills=skills,
        min_years_experience=years,
        keywords=keywords,
    )


def skill_gap(
    profile: SanitizedProfile, requirements: JobRequirements
) -> frozenset[str]:
    """Set A − Set B: required skills the profile is missing."""
    return requirements.required_skills - profile.skills


def skill_coverage_ratio(
    profile: SanitizedProfile, requirements: JobRequirements
) -> float:
    """Fraction of required skills that the profile already has (0.0 − 1.0)."""
    if not requirements.required_skills:
        return 0.0
    matched = requirements.required_skills & profile.skills
    return len(matched) / len(requirements.required_skills)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------


_EXPERIENCE_KEYS = ("experience", "work_experience", "roles")
_SKILL_KEYS = ("skills", "technologies", "tech_stack")


def _extract_skills(parsed_resume: Optional[Dict[str, Any]]) -> List[str]:
    """Collect + lowercase + dedupe every skill-ish string we can find."""
    if not parsed_resume:
        return []

    collected: List[str] = []
    for key in _SKILL_KEYS:
        value = parsed_resume.get(key)
        if not value:
            continue
        if isinstance(value, str):
            collected.extend(_split_skill_string(value))
        elif isinstance(value, Iterable):
            for item in value:
                if isinstance(item, str):
                    collected.append(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("skill")
                    if isinstance(name, str):
                        collected.append(name)

    seen: set[str] = set()
    result: List[str] = []
    for skill in collected:
        normalized = skill.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _split_skill_string(raw: str) -> List[str]:
    """Fallback splitter for comma- or slash-separated skill strings."""
    tokens = [part.strip() for chunk in raw.split(",") for part in chunk.split("/")]
    return [t for t in tokens if t]


def _compute_years_experience(parsed_resume: Optional[Dict[str, Any]]) -> float:
    """Derive total years from resume data.

    Preference order:
        1. Explicit ``total_years_experience`` field if the parser set one.
        2. Sum of per-role durations.
        3. 0.0 fallback.

    We avoid rounding too aggressively — 1.5 years is a real data point.
    """
    if not parsed_resume:
        return 0.0

    explicit = parsed_resume.get("total_years_experience")
    if isinstance(explicit, (int, float)) and explicit >= 0:
        return float(explicit)

    total = 0.0
    for key in _EXPERIENCE_KEYS:
        roles = parsed_resume.get(key)
        if not isinstance(roles, Sequence):
            continue
        for role in roles:
            if not isinstance(role, dict):
                continue
            duration = _parse_role_duration(role)
            if duration:
                total += duration
    return round(total, 2)


def _parse_role_duration(role: Dict[str, Any]) -> float:
    """Try several common duration representations, return years as float."""
    # Explicit years field.
    years = role.get("years") or role.get("duration_years")
    if isinstance(years, (int, float)) and years >= 0:
        return float(years)

    start = _as_date(role.get("start_date") or role.get("from"))
    end_raw = role.get("end_date") or role.get("to") or role.get("until")
    end = datetime.now().date() if _is_present_marker(end_raw) else _as_date(end_raw)

    if start and end and end >= start:
        delta_days = (end - start).days
        return delta_days / 365.25

    duration_str = role.get("duration")
    if isinstance(duration_str, str):
        return _parse_duration_string(duration_str)
    return 0.0


def _is_present_marker(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower() in {"present", "current", "now", "ongoing"}


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%m/%Y", "%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _parse_duration_string(raw: str) -> float:
    """Parse strings like '2020-2023' or '2020 - Present'."""
    raw = raw.strip()
    if "-" not in raw:
        return 0.0
    start_str, _, end_str = raw.partition("-")
    start = _as_date(start_str.strip())
    end_trim = end_str.strip()
    end = datetime.now().date() if _is_present_marker(end_trim) else _as_date(end_trim)
    if start and end and end >= start:
        return round((end - start).days / 365.25, 2)
    return 0.0


def _parse_years_requirement(description: str) -> float:
    """Scan JD text for '5+ years' / '3 years' patterns."""
    import re

    patterns = [
        r"(\d+)\s*\+\s*years",
        r"(\d+)\s*\+\s*yrs",
        r"(\d+)\s+years",
        r"(\d+)\s+yrs",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return 0.0
