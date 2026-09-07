from __future__ import annotations

from statistics import mean, median

from .models import ActiveMarketMetrics, MarketListing, MarketMatch, MatchLevel


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _pct(cherry_price: float, market_price: float | None) -> float | None:
    if market_price is None or market_price <= 0:
        return None

    return round((cherry_price - market_price) / market_price * 100.0, 2)


def _trimmed(values: list[float]) -> list[float]:
    if len(values) < 5:
        return values

    ordered = sorted(values)
    trim = max(1, int(len(ordered) * 0.10))

    return ordered[trim:-trim] or ordered


def calculate_active_metrics(
    source_listing_external_id: str,
    cherry_price_aud: float,
    market_listings: list[MarketListing],
    matches: list[MarketMatch],
) -> ActiveMarketMetrics:
    accepted_ids = {
        match.market_external_id
        for match in matches
        if match.match_level in {MatchLevel.EXACT, MatchLevel.STRONG}
    }
    exact_ids = {
        match.market_external_id
        for match in matches
        if match.match_level == MatchLevel.EXACT
    }
    strong_ids = {
        match.market_external_id
        for match in matches
        if match.match_level == MatchLevel.STRONG
    }

    aud_prices = sorted(
        (listing.landed_price_aud or 0.0)
        for listing in market_listings
        if listing.external_id in accepted_ids
        and listing.landed_price_aud is not None
        and listing.landed_price_aud > 0
    )

    if not aud_prices:
        return ActiveMarketMetrics(
            source_listing_external_id=source_listing_external_id,
            active_match_count=len(accepted_ids),
            active_exact_count=len(exact_ids),
            active_strong_count=len(strong_ids),
            status="NO_MARKET_MATCHES",
        )

    lowest = aud_prices[0]
    highest = aud_prices[-1]
    med = median(aud_prices)
    trimmed_values = _trimmed(aud_prices)
    trimmed_med = median(trimmed_values)
    avg = mean(trimmed_values)
    spread = (highest - lowest) / lowest * 100.0 if lowest > 0 else None
    discount_lowest = _pct(cherry_price_aud, lowest)
    discount_median = _pct(cherry_price_aud, med)

    if discount_median is not None and discount_median <= -15.0:
        status = "ACTIVE_MARKET_CHEAP"
    elif discount_median is not None and discount_median >= 15.0:
        status = "ACTIVE_MARKET_EXPENSIVE"
    else:
        status = "ACTIVE_MARKET_NORMAL"

    confidence = min(
        1.0,
        0.20
        + (len(exact_ids) * 0.18)
        + (len(strong_ids) * 0.08),
    )

    return ActiveMarketMetrics(
        source_listing_external_id=source_listing_external_id,
        active_match_count=len(accepted_ids),
        active_exact_count=len(exact_ids),
        active_strong_count=len(strong_ids),
        active_lowest_aud=_round(lowest),
        active_median_aud=_round(med),
        active_trimmed_median_aud=_round(trimmed_med),
        active_mean_aud=_round(avg),
        active_max_aud=_round(highest),
        active_market_spread=_round(spread),
        cherry_vs_active_lowest_pct=discount_lowest,
        cherry_vs_active_median_pct=discount_median,
        market_match_confidence=round(confidence, 3),
        status=status,
    )
