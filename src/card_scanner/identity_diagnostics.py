from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from .market_catalogue import MarketListingObservation


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def family_identity_gaps(observation: MarketListingObservation) -> tuple[str, ...]:
    """Explain why an active listing is not eligible for strict family matching."""

    identity = observation.listing.identity
    if identity is None:
        return ("NO_IDENTITY",)

    gaps: list[str] = []
    if not _present(identity.player):
        gaps.append("MISSING_PLAYER")
    if not _present(identity.year):
        gaps.append("MISSING_YEAR")
    if not (_present(identity.brand) or _present(identity.set_name)):
        gaps.append("MISSING_BRAND_OR_SET")
    if not (
        _present(identity.card_number)
        or _present(identity.parallel)
        or _present(identity.serial_total)
    ):
        gaps.append("MISSING_STRUCTURED_DISCRIMINATOR")
    return tuple(gaps)


def build_identity_diagnostics(
    observations: Iterable[MarketListingObservation],
) -> dict[str, Any]:
    rows = list(observations)
    gap_counts: Counter[str] = Counter()
    source_totals: Counter[str] = Counter()
    source_eligible: Counter[str] = Counter()
    source_gap_counts: dict[str, Counter[str]] = defaultdict(Counter)
    eligible = 0

    for observation in rows:
        source = observation.listing.source
        source_totals[source] += 1
        gaps = family_identity_gaps(observation)
        if not gaps:
            eligible += 1
            source_eligible[source] += 1
            continue
        for gap in gaps:
            gap_counts[gap] += 1
            source_gap_counts[source][gap] += 1

    by_source = []
    for source in sorted(source_totals):
        total = source_totals[source]
        source_eligible_count = source_eligible[source]
        by_source.append(
            {
                "source": source,
                "listing_count": total,
                "family_eligible_count": source_eligible_count,
                "family_eligible_pct": round((source_eligible_count / total) * 100.0, 1)
                if total
                else 0.0,
                "gap_counts": dict(sorted(source_gap_counts[source].items())),
            }
        )

    return {
        "listing_count": len(rows),
        "family_eligible_count": eligible,
        "family_ineligible_count": len(rows) - eligible,
        "family_eligible_pct": round((eligible / len(rows)) * 100.0, 1) if rows else 0.0,
        "gap_counts": dict(sorted(gap_counts.items())),
        "by_source": by_source,
        "interpretation": "DIAGNOSTIC_ONLY_DOES_NOT_RELAX_MATCHING_OR_VALUATION_GATES",
    }
