"""Parse season year CLI args: ``2026``, ``2024,2025,2026``, or multiple args."""

from __future__ import annotations

from typing import List


def parse_years(*raw_parts: str) -> List[int]:
    """Return unique years in the order first seen.

    Accepts comma- and/or whitespace-separated tokens across one or more args.
    Raises ValueError on empty input or non-integer tokens.
    """
    tokens: List[str] = []
    for part in raw_parts:
        if part is None:
            continue
        for tok in str(part).replace(" ", ",").split(","):
            tok = tok.strip()
            if tok:
                tokens.append(tok)
    if not tokens:
        raise ValueError("No year provided")
    years: List[int] = []
    seen = set()
    for tok in tokens:
        year = int(tok)
        if year not in seen:
            seen.add(year)
            years.append(year)
    return years
