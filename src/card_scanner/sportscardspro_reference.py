from __future__ import annotations

from typing import Any
from urllib.parse import urlencode


SEARCH_URL = "https://www.sportscardspro.com/search-products"


def exact_research_terms(group: dict[str, Any]) -> list[str]:
    """Build conservative SportsCardsPro search terms from an exact group.

    The individual serial copy number is intentionally excluded. The serial
    denominator is retained because /10 and /25 are different card variants.
    """
    listings = group.get("listings") or []
    sample = listings[0] if listings else {}
    terms = [
        group.get("year"),
        group.get("player"),
        group.get("product"),
        sample.get("card_number"),
        sample.get("parallel"),
    ]
    serial_total = sample.get("serial_total")
    if serial_total:
        terms.append(f"/{serial_total}")
    grader = sample.get("grader")
    grade = sample.get("grade")
    if grader:
        terms.append(grader)
    if grade:
        terms.append(grade)
    return [str(term).strip() for term in terms if term not in (None, "") and str(term).strip()]


def search_url_for_exact_group(group: dict[str, Any]) -> str:
    query = " ".join(exact_research_terms(group))
    return f"{SEARCH_URL}?{urlencode({'type': 'prices', 'q': query})}"
