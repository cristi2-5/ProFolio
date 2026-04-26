"""
Tests for the Token Guard utility (Phase 7 / QA — long JDs).

Pure functions, no dependencies — fully deterministic.
"""

from __future__ import annotations

import pytest

from app.utils.token_guard import (
    DEFAULT_JD_TOKEN_BUDGET,
    estimate_tokens,
    fits_in_budget,
    truncate_for_budget,
)


class TestEstimateTokens:
    def test_empty_string_returns_zero(self) -> None:
        assert estimate_tokens("") == 0

    def test_short_string_rounds_up(self) -> None:
        # 7 chars / 4 chars-per-token → ceil = 2 tokens.
        assert estimate_tokens("1234567") == 2

    def test_exact_multiple_matches(self) -> None:
        assert estimate_tokens("a" * 16) == 4

    @pytest.mark.parametrize(
        "text,expected_min",
        [
            ("Python developer with FastAPI experience", 8),
            ("a" * 4000, 1000),
            ("a" * 40000, 10000),
        ],
    )
    def test_scales_with_length(self, text: str, expected_min: int) -> None:
        assert estimate_tokens(text) >= expected_min


class TestTruncateForBudget:
    def test_short_input_passes_through(self) -> None:
        text = "Short JD text."
        result = truncate_for_budget(text, token_budget=100)
        assert result.was_truncated is False
        assert result.text == text
        assert result.estimated_tokens_in == result.estimated_tokens_out

    def test_long_input_gets_truncated(self) -> None:
        text = "A" * 20_000  # ~5000 tokens
        result = truncate_for_budget(text, token_budget=1000)
        assert result.was_truncated is True
        # Output respects the budget (with ~marker overhead tolerance).
        assert result.estimated_tokens_out <= 1000 + 20

    def test_truncation_preserves_head_and_tail(self) -> None:
        text = "HEAD" + ("x" * 30_000) + "TAIL"
        result = truncate_for_budget(text, token_budget=500)
        assert result.was_truncated is True
        assert result.text.startswith("HEAD")
        assert result.text.endswith("TAIL")
        assert "truncated" in result.text

    def test_zero_budget_raises(self) -> None:
        with pytest.raises(ValueError, match="token_budget"):
            truncate_for_budget("anything", token_budget=0)

    def test_invalid_head_ratio_raises(self) -> None:
        with pytest.raises(ValueError, match="head_ratio"):
            truncate_for_budget("abc", token_budget=100, head_ratio=0.0)
        with pytest.raises(ValueError, match="head_ratio"):
            truncate_for_budget("abc", token_budget=100, head_ratio=1.0)

    def test_head_ratio_controls_split(self) -> None:
        # Marker-plus-characters; head should dominate when ratio=0.9.
        text = "H" * 5_000 + "T" * 5_000
        result_head = truncate_for_budget(text, token_budget=200, head_ratio=0.9)
        head_portion, _, tail_portion = result_head.text.partition("content truncated")
        # Head chunk should be clearly longer than the tail when ratio=0.9.
        assert len(head_portion) > len(tail_portion) * 2

    def test_truncated_output_is_stable(self) -> None:
        text = "X" * 12_000
        result_a = truncate_for_budget(text, token_budget=500)
        result_b = truncate_for_budget(text, token_budget=500)
        assert result_a.text == result_b.text


class TestFitsInBudget:
    def test_true_for_short(self) -> None:
        assert fits_in_budget("abc", token_budget=10) is True

    def test_false_for_long(self) -> None:
        assert fits_in_budget("a" * 10_000, token_budget=100) is False


class TestDefaultBudget:
    def test_default_jd_budget_handles_realistic_jd(self) -> None:
        """A JD at the upper end of "normal" (~8k chars) should pass."""
        jd = "Typical JD content. " * 400  # ~8000 chars → ~2000 tokens
        result = truncate_for_budget(jd, token_budget=DEFAULT_JD_TOKEN_BUDGET)
        assert result.was_truncated is False
