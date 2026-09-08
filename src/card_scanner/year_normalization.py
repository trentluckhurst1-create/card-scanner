from __future__ import annotations

import re


SEASON_YEAR_RE = re.compile(
    r"^\s*((?:19|20)\d{2})\s*[-/]\s*(\d{2})\s*$"
)

SINGLE_YEAR_RE = re.compile(
    r"^\s*((?:19|20)\d{2})\s*$"
)


def normalize_card_year(
    year: str | None,
) -> str | None:
    """
    Return a conservative year key for comparisons.

    Single-card years and season years are deliberately distinct:
    2024 is not equivalent to 2024-25.
    """

    if year is None:
        return None

    text = str(year).strip()

    if not text:
        return None

    single = SINGLE_YEAR_RE.fullmatch(text)

    if single:
        return single.group(1)

    season = SEASON_YEAR_RE.fullmatch(text)

    if not season:
        return None

    start = int(season.group(1))
    suffix = int(season.group(2))
    century = start // 100 * 100
    end = century + suffix

    if end < start:
        end += 100

    if end != start + 1:
        return None

    return f"{start}-{end}"
