"""
Basic prompt-injection mitigation for user-controlled text.

Pair with structured prompts and output validation — this is a
defense-in-depth layer, not a full mitigation.
"""

from __future__ import annotations

import re

# Patterns we redact from user-controlled text before forwarding to the
# LLM. Each is matched case-insensitively (see ``_INSTRUCTION_RE``).
# Order matters: longer/more specific phrases first so the substitution
# eats them whole rather than letting a shorter match win partial bites.
_INSTRUCTION_PATTERNS: tuple[str, ...] = (
    r"ignore (all )?previous instructions",
    r"disregard (all )?previous instructions",
    r"forget (everything|all)",
    r"system prompt",
)

# Single compiled regex covering every pattern above — one pass over the
# input keeps the sanitiser O(n) instead of O(n·k).
_INSTRUCTION_RE = re.compile("|".join(_INSTRUCTION_PATTERNS), re.IGNORECASE)

# HTML-like role tags are stripped to empty so a forged ``</system>``
# inside a CV cannot close the wrap_user_content boundary.
_TAG_RE = re.compile(r"</?(system|user|assistant)>", re.IGNORECASE)

# Visible marker we drop in place of stripped instructions. We replace
# rather than delete so the LLM can see that *something* was scrubbed —
# a silent drop would let an attacker shape the surrounding context.
_REDACTED_MARKER = "[redacted-instruction]"


def sanitize_user_text(text: str, *, max_chars: int = 50_000) -> str:
    """Defang potential prompt-injection vectors in user-controlled text.

    Performs three passes:
      1. Truncate to ``max_chars`` to bound LLM token cost on huge inputs.
      2. Drop ``<system>`` / ``<user>`` / ``<assistant>`` tags so user
         content can't forge wrap_user_content boundaries.
      3. Redact known instruction-style phrases (``ignore previous
         instructions``, etc.) with a visible marker.

    Not a full mitigation — pair with structured prompts and output
    validation. The deterministic eval at
    ``evals/deterministic/test_prompt_injection_resistance.py`` pins
    the contract that legitimate content survives unchanged while these
    patterns do not.
    """
    if not text:
        return ""
    text = text[:max_chars]
    text = _TAG_RE.sub("", text)
    text = _INSTRUCTION_RE.sub(_REDACTED_MARKER, text)
    return text


def wrap_user_content(label: str, content: str) -> str:
    """Wrap user-controlled content in clear delimiters for the LLM."""
    return (
        f"--- BEGIN {label} (user-supplied, untrusted) ---\n"
        f"{content}\n"
        f"--- END {label} ---"
    )
