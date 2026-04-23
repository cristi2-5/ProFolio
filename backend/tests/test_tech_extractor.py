"""
Tests for the Technology Extractor utility (Phase 5 / Epic 4 — US 4.2).

The extractor is deterministic, so tests are table-driven with no mocking.
"""

from __future__ import annotations

import pytest

from app.utils.tech_extractor import (
    ExtractedTech,
    extract_technologies,
    group_by_category,
)


class TestExtractTechnologies:
    """Behavior of ``extract_technologies``."""

    def test_empty_input_returns_empty_list(self) -> None:
        assert extract_technologies("") == []
        assert extract_technologies("   ") == []

    def test_picks_up_explicit_mentions(self) -> None:
        jd = "We need a Python developer familiar with FastAPI and PostgreSQL."
        names = {t.name for t in extract_technologies(jd)}
        assert {"Python", "FastAPI", "PostgreSQL"}.issubset(names)

    def test_word_boundaries_avoid_false_positives(self) -> None:
        # "java" must NOT match inside "javascript", and vice-versa.
        jd = "JavaScript and TypeScript experience required."
        names = {t.name for t in extract_technologies(jd)}
        assert "JavaScript" in names
        assert "TypeScript" in names
        assert "Java" not in names

    def test_case_insensitive_aliases(self) -> None:
        jd = "REACT and react.js are interchangeable here. Also REACTJS."
        techs = extract_technologies(jd)
        react = next(t for t in techs if t.name == "React")
        assert react.mentions == 3

    def test_ranked_by_mention_count_desc(self) -> None:
        jd = "Python Python Python React Docker"
        techs = extract_technologies(jd)
        assert techs[0].name == "Python"
        assert techs[0].mentions == 3
        assert techs[1].mentions == 1

    def test_tie_break_alphabetical(self) -> None:
        jd = "Python and Java are both good."
        techs = extract_technologies(jd)
        # Both have 1 mention; alphabetical order: Java < Python
        assert techs[0].name == "Java"
        assert techs[1].name == "Python"

    def test_respects_max_results(self) -> None:
        jd = (
            "Python, JavaScript, TypeScript, Go, Rust, Java, Kotlin, "
            "Swift, React, Vue.js, Angular, Docker, Kubernetes, AWS, Azure"
        )
        techs = extract_technologies(jd, max_results=5)
        assert len(techs) == 5

    def test_categories_assigned(self) -> None:
        jd = "Python, React, PostgreSQL, AWS, Docker"
        techs = {t.name: t.category for t in extract_technologies(jd)}
        assert techs["Python"] == "languages"
        assert techs["React"] == "frontend"
        assert techs["PostgreSQL"] == "databases"
        assert techs["AWS"] == "cloud"
        assert techs["Docker"] == "devops"

    def test_compound_names_like_nodejs(self) -> None:
        jd = "Backend: Node.js with Express and MongoDB"
        names = {t.name for t in extract_technologies(jd)}
        assert {"Node.js", "Express", "MongoDB"}.issubset(names)

    def test_special_char_techs(self) -> None:
        jd = "Looking for C++ and C# engineers."
        names = {t.name for t in extract_technologies(jd)}
        assert "C++" in names
        assert "C#" in names

    def test_deterministic(self) -> None:
        jd = "Python, React, Docker — must have all three."
        first = extract_technologies(jd)
        second = extract_technologies(jd)
        assert first == second


class TestGroupByCategory:
    """Behavior of ``group_by_category``."""

    def test_empty_input(self) -> None:
        assert group_by_category([]) == {}

    def test_groups_preserve_order(self) -> None:
        techs = [
            ExtractedTech("Python", "languages", 5),
            ExtractedTech("Go", "languages", 3),
            ExtractedTech("React", "frontend", 2),
        ]
        grouped = group_by_category(techs)
        assert grouped == {
            "languages": ["Python", "Go"],
            "frontend": ["React"],
        }

    @pytest.mark.parametrize(
        "input_categories",
        [
            ["frontend", "backend", "frontend"],
            ["languages", "languages", "cloud"],
        ],
    )
    def test_multiple_entries_per_category(self, input_categories: list[str]) -> None:
        techs = [
            ExtractedTech(f"Tech{i}", cat, 1)
            for i, cat in enumerate(input_categories)
        ]
        grouped = group_by_category(techs)
        assert sum(len(v) for v in grouped.values()) == len(input_categories)
