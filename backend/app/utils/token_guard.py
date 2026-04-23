"""
Token Guard — LLM token-budget protection.

Agents truncate long inputs (especially JDs) before forwarding to the LLM.
Pure functions only; no OpenAI dependency — we approximate token counts
from character length (~4 chars/token for English, which is the standard
heuristic OpenAI publishes) so this stays testable without the network.

Why a head+tail truncation strategy?
    Job descriptions tend to pack the meaningful signal at the start
    ("Role: Senior Backend Engineer. Stack: Python, FastAPI…") and at
    the end ("We offer equity, flexible hours, etc."). The middle is
    usually boilerplate "responsibilities" bullets. Keeping both ends
    preserves more useful content than a simple left-truncate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# OpenAI's widely cited rule of thumb: 1 token ≈ 4 English characters.
# This is intentionally a fixed constant (not tiktoken) so the module has
# zero runtime dependencies and is deterministic in tests.
_CHARS_PER_TOKEN: Final[float] = 4.0

# Budget defaults for the agents. Not hard limits on the model — these are
# the share of the context window we're willing to spend on a single field
# (JD text) so the rest of the prompt still fits comfortably.
DEFAULT_JD_TOKEN_BUDGET: Final[int] = 3000
DEFAULT_CV_TOKEN_BUDGET: Final[int] = 4000

# Sentinel inserted between head and tail when we truncate. Chosen to be
# short and explicit so the LLM can see what happened.
_TRUNCATION_MARKER: Final[str] = "\n\n[… content truncated for token budget …]\n\n"


@dataclass(frozen=True)
class TruncationResult:
    """Outcome of a truncation call — useful for logging/telemetry."""

    text: str
    was_truncated: bool
    estimated_tokens_in: int
    estimated_tokens_out: int


def estimate_tokens(text: str) -> int:
    """Approximate OpenAI token count for English text.

    Simple ceil-division by the published char/token ratio. Good enough
    for budget decisions; actual tokenization happens on the OpenAI side.
    """
    if not text:
        return 0
    return int(-(-len(text) // _CHARS_PER_TOKEN))  # ceil division


def truncate_for_budget(
    text: str,
    *,
    token_budget: int = DEFAULT_JD_TOKEN_BUDGET,
    head_ratio: float = 0.6,
) -> TruncationResult:
    """Truncate text to fit ``token_budget`` using a head+tail strategy.

    When the input exceeds the budget, we keep the first
    ``head_ratio`` of the budget from the start and the remaining budget
    from the end, joined by a visible marker. Short inputs pass through
    unchanged.

    Args:
        text: Content to truncate (typically a JD).
        token_budget: Max tokens to allow in the output.
        head_ratio: Fraction of the remaining budget reserved for the
            head of the text. Default 0.6 — JDs tend to lead with stack
            + seniority, which is the highest-signal section.

    Returns:
        ``TruncationResult`` with the (possibly truncated) text and
        counts suitable for logging.
    """
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    if not 0.0 < head_ratio < 1.0:
        raise ValueError("head_ratio must be between 0 and 1 (exclusive)")

    original_tokens = estimate_tokens(text)
    if original_tokens <= token_budget:
        return TruncationResult(
            text=text,
            was_truncated=False,
            estimated_tokens_in=original_tokens,
            estimated_tokens_out=original_tokens,
        )

    marker_tokens = estimate_tokens(_TRUNCATION_MARKER)
    usable_tokens = max(token_budget - marker_tokens, 1)

    head_tokens = int(usable_tokens * head_ratio)
    tail_tokens = usable_tokens - head_tokens

    head_chars = int(head_tokens * _CHARS_PER_TOKEN)
    tail_chars = int(tail_tokens * _CHARS_PER_TOKEN)

    head = text[:head_chars]
    tail = text[-tail_chars:] if tail_chars > 0 else ""

    truncated = f"{head}{_TRUNCATION_MARKER}{tail}"
    return TruncationResult(
        text=truncated,
        was_truncated=True,
        estimated_tokens_in=original_tokens,
        estimated_tokens_out=estimate_tokens(truncated),
    )


def fits_in_budget(text: str, *, token_budget: int) -> bool:
    """Check whether ``text`` is small enough to pass through untouched."""
    return estimate_tokens(text) <= token_budget
