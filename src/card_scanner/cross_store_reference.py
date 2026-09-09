from __future__ import annotations

from statistics import median

from .market_matching import assess_match
from .market_reference import (
    CrossStoreReference,
    MarketReferencePoint,
    MarketReferenceStatus,
)
from .models import Listing, MatchLevel
from .risk import title_risk_flags


ACCEPTED_MATCH_LEVELS = {
    MatchLevel.EXACT,
    MatchLevel.STRONG,
}


def _norm(value: object | None) -> str | None:
    if value is None:
        return None

    text = " ".join(str(value).casefold().split()).strip()
    return text or None


def _same_known_card_number(
    candidate: Listing,
    reference: Listing,
) -> bool:
    if candidate.identity is None or reference.identity is None:
        return False

    left = _norm(candidate.identity.card_number)
    right = _norm(reference.identity.card_number)

    if left is not None and right is not None and left != right:
        return False

    return True


def _same_source_item(
    candidate: Listing,
    reference: Listing,
) -> bool:
    return (
        candidate.source.casefold() == reference.source.casefold()
        and candidate.external_id == reference.external_id
    )


def _same_source(
    candidate: Listing,
    reference: Listing,
) -> bool:
    return candidate.source.casefold() == reference.source.casefold()


def _landed_aud(listing: Listing) -> float | None:
    if listing.currency.upper() != "AUD":
        return None

    price = float(listing.price)
    shipping = float(listing.shipping or 0.0)
    landed = price + shipping

    if landed <= 0:
        return None

    return round(landed, 2)


def _active_price_dispersion(
    prices: tuple[float, ...],
) -> tuple[float | None, float | None]:
    if not prices:
        return None, None

    baseline = float(median(prices))
    if baseline <= 0:
        return None, None

    spread = (max(prices) - min(prices)) / baseline * 100.0
    deviations = tuple(abs(price - baseline) for price in prices)
    mad = float(median(deviations)) / baseline * 100.0

    return round(spread, 2), round(mad, 2)


def _consensus_strength(
    *,
    source_count: int,
    matched_count: int,
    exact_count: int,
    mad_pct: float | None,
) -> tuple[float, str]:
    if source_count < 2 or matched_count < 2:
        return 0.0, "NO_CONSENSUS"

    breadth = min(source_count / 3.0, 1.0)
    exact_share = exact_count / matched_count if matched_count else 0.0

    if mad_pct is None:
        dispersion = 0.0
    elif mad_pct <= 10.0:
        dispersion = 1.0
    elif mad_pct <= 20.0:
        dispersion = 0.75
    elif mad_pct <= 35.0:
        dispersion = 0.45
    else:
        dispersion = 0.15

    strength = round(
        (0.40 * breadth)
        + (0.35 * exact_share)
        + (0.25 * dispersion),
        3,
    )

    if strength >= 0.80:
        level = "STRONG"
    elif strength >= 0.60:
        level = "MODERATE"
    else:
        level = "WEAK"

    return strength, level


def build_cross_store_reference(
    candidate: Listing,
    references: list[Listing],
) -> CrossStoreReference:
    candidate_landed = _landed_aud(candidate)

    if candidate_landed is None:
        raise ValueError(
            "cross-store reference candidate must have positive AUD landed cost"
        )

    if candidate.identity is None:
        return _empty_reference(
            candidate=candidate,
            candidate_landed=candidate_landed,
        )

    points: list[MarketReferencePoint] = []
    seen: set[tuple[str, str]] = set()

    for reference in references:
        key = (
            reference.source.casefold(),
            reference.external_id,
        )

        if key in seen:
            continue

        seen.add(key)

        if _same_source_item(candidate, reference):
            continue

        # V1 is deliberately cross-store only.
        if _same_source(candidate, reference):
            continue

        if reference.identity is None:
            continue

        landed = _landed_aud(reference)

        if landed is None:
            continue

        risk_flags = title_risk_flags(reference.title)

        assessment = assess_match(
            candidate.identity,
            reference.identity,
            risk_flags=risk_flags,
        )

        if assessment.match_level not in ACCEPTED_MATCH_LEVELS:
            continue

        # Cross-store reference is stricter than generic market matching.
        # A known card-number mismatch must never become a reference point.
        if not _same_known_card_number(candidate, reference):
            continue

        points.append(
            MarketReferencePoint(
                source=reference.source,
                external_id=reference.external_id,
                url=reference.url,
                price_aud=float(reference.price),
                shipping_aud=float(reference.shipping or 0.0),
                landed_aud=landed,
                title=reference.title,
                identity=reference.identity,
                match_level=assessment.match_level.value,
            )
        )

    if not points:
        return _empty_reference(
            candidate=candidate,
            candidate_landed=candidate_landed,
        )

    prices = tuple(
        sorted(point.landed_aud for point in points)
    )
    reference_sources = tuple(
        sorted({point.source for point in points})
    )

    exact_count = sum(
        point.match_level == MatchLevel.EXACT.value
        for point in points
    )
    strong_count = sum(
        point.match_level == MatchLevel.STRONG.value
        for point in points
    )

    median_price = float(median(prices))
    active_spread_pct, active_mad_pct = _active_price_dispersion(prices)
    lowest_price = min(prices)
    discount_to_lowest = (
        (lowest_price - candidate_landed)
        / lowest_price
        * 100.0
        if lowest_price > 0
        else None
    )

    discount_pct = (
        (median_price - candidate_landed)
        / median_price
        * 100.0
        if median_price > 0
        else None
    )

    source_count = len(reference_sources)

    # Active asks are corroborative evidence only.
    # Confidence measures breadth/quality of active references,
    # not valuation confidence.
    match_quality = (
        exact_count + (0.75 * strong_count)
    ) / len(points)

    depth_factor = min(len(points) / 3.0, 1.0)
    source_factor = min(source_count / 2.0, 1.0)

    confidence = round(
        min(
            1.0,
            (0.50 * match_quality)
            + (0.25 * depth_factor)
            + (0.25 * source_factor),
        ),
        3,
    )

    consensus_strength, consensus_level = _consensus_strength(
        source_count=source_count,
        matched_count=len(points),
        exact_count=exact_count,
        mad_pct=active_mad_pct,
    )

    status = (
        MarketReferenceStatus.REFERENCE_AVAILABLE
        if len(points) >= 2 and source_count >= 2
        else MarketReferenceStatus.INSUFFICIENT_REFERENCE
    )

    return CrossStoreReference(
        candidate_source=candidate.source,
        candidate_external_id=candidate.external_id,
        candidate_landed_aud=candidate_landed,
        matched_listing_count=len(points),
        exact_match_count=exact_count,
        strong_match_count=strong_count,
        source_count=source_count,
        reference_sources=reference_sources,
        reference_prices_aud=prices,
        min_reference_price_aud=min(prices),
        median_reference_price_aud=round(median_price, 2),
        max_reference_price_aud=max(prices),
        candidate_discount_to_median_pct=(
            round(discount_pct, 2)
            if discount_pct is not None
            else None
        ),
        confidence=confidence,
        active_price_spread_pct=active_spread_pct,
        active_mad_pct=active_mad_pct,
        candidate_discount_to_lowest_pct=(
            round(discount_to_lowest, 2)
            if discount_to_lowest is not None
            else None
        ),
        consensus_strength=consensus_strength,
        consensus_level=consensus_level,
        status=status,
    )


def _empty_reference(
    candidate: Listing,
    candidate_landed: float,
) -> CrossStoreReference:
    return CrossStoreReference(
        candidate_source=candidate.source,
        candidate_external_id=candidate.external_id,
        candidate_landed_aud=candidate_landed,
        matched_listing_count=0,
        exact_match_count=0,
        strong_match_count=0,
        source_count=0,
        reference_sources=(),
        reference_prices_aud=(),
        min_reference_price_aud=None,
        median_reference_price_aud=None,
        max_reference_price_aud=None,
        candidate_discount_to_median_pct=None,
        confidence=0.0,
        status=MarketReferenceStatus.NO_REFERENCE,
    )
