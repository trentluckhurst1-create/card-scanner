from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from .candidate_discovery import assess_candidate_discovery
from .market_catalogue import MarketListingObservation
from .sold_comp_engine import MIN_SOLD_COMP_IDENTITY_QUALITY


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


def _sold_not_ready_reasons(observation: MarketListingObservation, assessment) -> tuple[str, ...]:
    """Return diagnostic reasons using the governed discovery assessment.

    These reasons explain readiness only. They do not change the underlying
    threshold, family eligibility, valuation, or BUY/STRONG_BUY gates.
    """

    if assessment.sold_comp_ready:
        return ()

    reasons: list[str] = []
    if assessment.underdescription.status == "NOT_APPLICABLE":
        reasons.append("NON_CARD_PRODUCT")

    identity = observation.listing.identity
    if identity is None:
        reasons.append("NO_IDENTITY")
        return tuple(reasons)

    if not _present(identity.player):
        reasons.append("PLAYER_IDENTITY_MISSING")

    if assessment.identity_quality < MIN_SOLD_COMP_IDENTITY_QUALITY:
        reasons.append("IDENTITY_BELOW_SOLD_THRESHOLD")

    # Contributors are intentionally descriptive rather than requirements:
    # comp_quality is additive and no single one of these fields is mandatory.
    if not _present(identity.year):
        reasons.append("MISSING_YEAR")
    if not (_present(identity.brand) or _present(identity.set_name)):
        reasons.append("MISSING_BRAND_OR_SET")
    if not _present(identity.card_number):
        reasons.append("MISSING_CARD_NUMBER")
    if not _present(identity.parallel):
        reasons.append("MISSING_PARALLEL")
    if not _present(identity.serial_total):
        reasons.append("MISSING_SERIAL_TOTAL")

    return tuple(reasons)


def _quality_band(value: float) -> str:
    if value < 0.40:
        return "BELOW_0_40"
    if value < 0.60:
        return "0_40_TO_0_59"
    if value < MIN_SOLD_COMP_IDENTITY_QUALITY:
        return "0_60_TO_0_69"
    return "0_70_PLUS"


def build_identity_diagnostics(
    observations: Iterable[MarketListingObservation],
) -> dict[str, Any]:
    rows = list(observations)
    gap_counts: Counter[str] = Counter()
    source_totals: Counter[str] = Counter()
    source_eligible: Counter[str] = Counter()
    source_gap_counts: dict[str, Counter[str]] = defaultdict(Counter)
    source_sold_ready: Counter[str] = Counter()
    source_sold_reasons: dict[str, Counter[str]] = defaultdict(Counter)
    source_quality_total: Counter[str] = Counter()
    sold_reason_counts: Counter[str] = Counter()
    quality_bands: Counter[str] = Counter()
    eligible = 0
    sold_ready = 0

    for observation in rows:
        source = observation.listing.source
        source_totals[source] += 1

        gaps = family_identity_gaps(observation)
        if not gaps:
            eligible += 1
            source_eligible[source] += 1
        else:
            for gap in gaps:
                gap_counts[gap] += 1
                source_gap_counts[source][gap] += 1

        assessment = assess_candidate_discovery(
            observation.listing,
            observation.history,
        )
        quality_bands[_quality_band(float(assessment.identity_quality))] += 1
        source_quality_total[source] += float(assessment.identity_quality)

        if assessment.sold_comp_ready:
            sold_ready += 1
            source_sold_ready[source] += 1
        else:
            reasons = _sold_not_ready_reasons(observation, assessment)
            for reason in reasons:
                sold_reason_counts[reason] += 1
                source_sold_reasons[source][reason] += 1

    by_source = []
    for source in sorted(source_totals):
        total = source_totals[source]
        source_eligible_count = source_eligible[source]
        source_sold_ready_count = source_sold_ready[source]
        by_source.append(
            {
                "source": source,
                "listing_count": total,
                "family_eligible_count": source_eligible_count,
                "family_eligible_pct": round((source_eligible_count / total) * 100.0, 1)
                if total
                else 0.0,
                "gap_counts": dict(sorted(source_gap_counts[source].items())),
                "sold_research_ready_count": source_sold_ready_count,
                "sold_research_not_ready_count": total - source_sold_ready_count,
                "sold_research_ready_pct": round((source_sold_ready_count / total) * 100.0, 1)
                if total
                else 0.0,
                "sold_not_ready_reason_counts": dict(
                    sorted(source_sold_reasons[source].items())
                ),
                "mean_identity_quality": round(source_quality_total[source] / total, 3)
                if total
                else 0.0,
            }
        )

    return {
        "listing_count": len(rows),
        "family_eligible_count": eligible,
        "family_ineligible_count": len(rows) - eligible,
        "family_eligible_pct": round((eligible / len(rows)) * 100.0, 1) if rows else 0.0,
        "gap_counts": dict(sorted(gap_counts.items())),
        "sold_identity_quality_threshold": MIN_SOLD_COMP_IDENTITY_QUALITY,
        "sold_research_ready_count": sold_ready,
        "sold_research_not_ready_count": len(rows) - sold_ready,
        "sold_research_ready_pct": round((sold_ready / len(rows)) * 100.0, 1) if rows else 0.0,
        "sold_not_ready_reason_counts": dict(sorted(sold_reason_counts.items())),
        "identity_quality_bands": dict(sorted(quality_bands.items())),
        "by_source": by_source,
        "interpretation": "DIAGNOSTIC_ONLY_DOES_NOT_RELAX_MATCHING_OR_VALUATION_GATES",
    }
