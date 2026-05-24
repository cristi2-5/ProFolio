"""Fabrication token-set — heuristic detector remains usefully strict.

The CV Optimizer ships a heuristic ``_detect_potential_fabrications``
that flags tech-looking tokens in the optimized output that don't appear
in the original CV's skill list. The flagged list is surfaced to the
caller as ``potential_fabrications`` and is the **deterministic** half
of the NO_FABRICATION contract (the semantic half is the LLM-as-judge
in Phase 3).

This deterministic eval pins the detector's behavior on a fixed corpus
of (original_skills, optimized_text) pairs. A regression in the detector
— widening stopwords, loosening the tech-suffix heuristic, etc. — would
silently weaken the deterministic floor. These tests fail loudly.
"""

from __future__ import annotations

import pytest

from app.agents.cv_optimizer import CVOptimizerAgent


pytestmark = pytest.mark.eval


@pytest.fixture
def agent() -> CVOptimizerAgent:
    """Bare CVOptimizerAgent — no LLM calls, just heuristics."""
    return CVOptimizerAgent()


# ----------------------------------------------------------------------
# Positive cases — fabrications must be flagged
# ----------------------------------------------------------------------


def test_detects_brand_new_tech_token(agent: CVOptimizerAgent) -> None:
    """LLM introduced ``Kubernetes`` even though the CV never mentioned it."""
    flagged = agent._detect_potential_fabrications(
        original_skills=["Python", "FastAPI"],
        optimized_text="Engineered Python services on Kubernetes clusters.",
    )
    assert "Kubernetes" in flagged, f"detector missed Kubernetes: {flagged}"


def test_detects_dotted_tech_name(agent: CVOptimizerAgent) -> None:
    """``Node.js`` / ``.NET`` style names must trigger the heuristic."""
    flagged = agent._detect_potential_fabrications(
        original_skills=["Python"],
        optimized_text="Built Node.js APIs alongside Python services.",
    )
    lowered = {token.lower() for token in flagged}
    assert "node.js" in lowered, f"missed dotted name: {flagged}"


def test_detects_internalcap_tech_name(agent: CVOptimizerAgent) -> None:
    """``GraphQL`` / ``MongoDB`` style camel-cased names."""
    flagged = agent._detect_potential_fabrications(
        original_skills=["REST"],
        optimized_text="Migrated to GraphQL with MongoDB persistence.",
    )
    flagged_lower = {token.lower() for token in flagged}
    assert "graphql" in flagged_lower and "mongodb" in flagged_lower, flagged


# ----------------------------------------------------------------------
# Negative cases — stopwords and originals must not be flagged
# ----------------------------------------------------------------------


def test_does_not_flag_original_skills(agent: CVOptimizerAgent) -> None:
    """Skills already in the original CV are not fabrications."""
    flagged = agent._detect_potential_fabrications(
        original_skills=["Python", "FastAPI", "PostgreSQL"],
        optimized_text="Engineered Python and FastAPI services on PostgreSQL.",
    )
    assert flagged == [], f"original skills wrongly flagged: {flagged}"


def test_does_not_flag_common_english_filler(agent: CVOptimizerAgent) -> None:
    """Words like ``Developed``, ``Implemented`` etc. must stay quiet."""
    flagged = agent._detect_potential_fabrications(
        original_skills=["Python"],
        optimized_text=(
            "Developed scalable services. Implemented new features. "
            "Improved performance. Drove team adoption. Owned backend."
        ),
    )
    # Sentence-initial uppercase common-English words must be stopworded.
    assert flagged == [], f"common filler wrongly flagged: {flagged}"


def test_handles_empty_input(agent: CVOptimizerAgent) -> None:
    assert agent._detect_potential_fabrications([], "") == []
    assert agent._detect_potential_fabrications(["Python"], "") == []
    assert agent._detect_potential_fabrications([], "Python work.") != []


# ----------------------------------------------------------------------
# Edge cases — case insensitivity, deduplication, punctuation
# ----------------------------------------------------------------------


def test_deduplicates_repeated_flags(agent: CVOptimizerAgent) -> None:
    """Mentioning ``Kubernetes`` four times yields one flag, not four."""
    text = "Kubernetes work. More Kubernetes. Even more Kubernetes. And again Kubernetes."
    flagged = agent._detect_potential_fabrications(
        original_skills=["Python"],
        optimized_text=text,
    )
    lowered = [t.lower() for t in flagged]
    assert lowered.count("kubernetes") == 1, lowered


def test_case_insensitive_match_against_originals(agent: CVOptimizerAgent) -> None:
    """``python`` in output vs ``Python`` in originals — same token."""
    flagged = agent._detect_potential_fabrications(
        original_skills=["Python"],
        optimized_text="python and Python and PYTHON work.",
    )
    assert flagged == []


def test_strips_trailing_punctuation_before_match(agent: CVOptimizerAgent) -> None:
    """``Docker,`` and ``Docker.`` must compare equal to ``Docker``."""
    flagged = agent._detect_potential_fabrications(
        original_skills=["Docker"],
        optimized_text="Built with Docker, Docker. Docker; Docker:",
    )
    assert flagged == []
