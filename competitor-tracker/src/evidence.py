"""Deterministic verbatim evidence verification against snapshot source text."""

from __future__ import annotations

import re


def normalize_ws(text: str) -> str:
    """Collapse all whitespace runs to a single space, strip, and lowercase."""
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_quote(quote: str, source_text: str) -> bool:
    """Verify that quote (>= 15 chars) appears verbatim in source_text modulo whitespace/case."""
    if not isinstance(quote, str) or not isinstance(source_text, str):
        return False
    stripped = quote.strip()
    if len(stripped) < 15:
        return False
    norm_quote = normalize_ws(stripped)
    if len(norm_quote) < 15:
        return False
    return norm_quote in normalize_ws(source_text)
