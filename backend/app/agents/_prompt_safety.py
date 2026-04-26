"""
Basic prompt-injection mitigation for user-controlled text.

Pair with structured prompts and output validation — this is a
defense-in-depth layer, not a full mitigation.
"""

from __future__ import annotations

import re

_INSTRUCTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"disregard (all )?previous instructions",
    r"forget (everything|all)",
    r"system prompt",
    r"</?system>",
    r"</?user>",
    r"</?assistant>",
]


def sanitize_user_text(text: str, *, max_chars: int = 50_000) -> str:
    """Defang potential prompt-injection vectors in user-controlled text.

    Truncates to max_chars and removes/escapes obvious injection patterns.
    Not a full mitigation — pair with structured prompts and output validation.
    """
    if not text:
        return ""
    text = text[:max_chars]
    text = re.sub(r"</?(system|user|assistant)>", "", text, flags=re.IGNORECASE)
    return text


def wrap_user_content(label: str, content: str) -> str:
    """Wrap user-controlled content in clear delimiters for the LLM."""
    return (
        f"--- BEGIN {label} (user-supplied, untrusted) ---\n"
        f"{content}\n"
        f"--- END {label} ---"
    )
