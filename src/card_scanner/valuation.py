from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean, median
from typing import Iterable

from .config import settings
from .models import MatchLevel, SoldComp, SoldCompMatch, SoldValuation


@dataclass
class Comp:
    sold_price_aud: float
    age_days: float
    similarity: float


def robust_fair_value(comps: Iterable[Comp]) -> tuple[float | None, float, int]:
    comps = [c for c in comps if c.sold_price_aud > 0 and c.similarity > 0]
    if not comps:
        return None, 0.0, 0

    weighted = []
    for c in comps:
        recency = max(0.25, 1.0 / (1.0 + c.age_days / 90.0))
        weight = c.similarity * recency
        repeats = max(1, round(weight * 10))
        weighted.extend([c.sold_price_aud] * repeats)

    fair = median(weighted)
    avg_similarity = sum(c.similarity for c in comps) / len(comps)
    depth = min(len(comps) / 8.0, 1.0)
    confidence = min(1.0, 0.65 * avg_similarity + 0.35 * depth)
    return round(fair, 2), round(confidence, 3), len(comps)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _age_days(sold_date: str, as_of: date) -> int | None:
    parsed = _parse_date(sold_date)
    if parsed is None:
        return None

    return max(0, (as_of - parsed).days)


def _median(values: list[float]) -> float | None:
    return round(median(values), 2) if values else None


def _iqr_filter(values: list[float]) -> list[float]:
    if len(values) < 4:
        return values

    ordered = sorted(values)
    midpoint = len(ordered) // 2
    lower_half = ordered[:midpoint]
    upper_half = ordered[midpoint + (len(ordered) % 2):]
    q1 = median(lower_half)
    q3 = median(upper_half)
    iqr = q3 - q1

    if iqr <= 0:
        return ordered

    lower_bound = q1 - settings.outlier_iqr_multiplier * iqr
    upper_bound = q3 + settings.outlier_iqr_multiplier * iqr

    return [
        value
        for value in ordered
        if lower_bound <= value <= upper_bound
    ]


def _weighted_median(records: list[dict]) -> float | None:
    if not records:
        return None

    expanded: list[float] = []

    for record in records:
        age_days = record["age_days"]
        recency = max(0.25, 1.0 / (1.0 + age_days / 90.0))
        weight = record["match_score"] * recency
        repeats = max(1, round(weight * 10))
        expanded.extend([record["price"]] * repeats)

    return round(median(expanded), 2)


def _price_spread_pct(values: list[float]) -> float | None:
    baseline = median(values) if values else None

    if baseline is None or baseline <= 0:
        return None

    return round((max(values) - min(values)) / baseline * 100.0, 2)


def _median_absolute_deviation_pct(values: list[float]) -> float | None:
    if not values:
        return None

    baseline = median(values)

    if baseline <= 0:
        return None

    deviations = [
        abs(value - baseline)
        for value in values
    ]

    return round(median(deviations) / baseline * 100.0, 2)


def _age_metrics(records: list[dict]) -> dict[str, float | int | None]:
    ages = [
        int(record["age_days"])
        for record in records
    ]

    if not ages:
        return {
            "newest_comp_age_days": None,
            "oldest_comp_age_days": None,
            "median_comp_age_days": None,
        }

    return {
        "newest_comp_age_days": min(ages),
        "oldest_comp_age_days": max(ages),
        "median_comp_age_days": round(median(ages), 1),
    }


def _market_direction(records: list[dict]) -> tuple[str, str]:
    recent = [
        record["price"]
        for record in records
        if record["age_days"] <= 90
    ]
    prior = [
        record["price"]
        for record in records
        if 90 < record["age_days"] <= 180
    ]

    if len(recent) < 3 or len(prior) < 3:
        return "INSUFFICIENT_DATA", "requires at least three sales in both recent and prior windows"

    recent_median = median(recent)
    prior_median = median(prior)

    if prior_median <= 0:
        return "INSUFFICIENT_DATA", "prior median is not usable"

    change_pct = (recent_median - prior_median) / prior_median * 100.0

    if change_pct >= 12.0:
        return "RISING", f"90-day median is {change_pct:.1f}% above prior 90-day median"

    if change_pct <= -12.0:
        return "FALLING", f"90-day median is {abs(change_pct):.1f}% below prior 90-day median"

    return "STABLE", f"90-day median changed {change_pct:.1f}% versus prior window"


def value_from_sold_comps(
    source_listing_external_id: str,
    comp_matches: list[tuple[SoldComp, SoldCompMatch]],
    as_of: date | None = None,
) -> SoldValuation:
    as_of = as_of or date.today()
    accepted: list[dict] = []
    counts = {
        MatchLevel.EXACT: 0,
        MatchLevel.STRONG: 0,
        MatchLevel.RELATED: 0,
    }

    for comp, match in comp_matches:
        level = match.match_level
        if not isinstance(level, MatchLevel):
            level = MatchLevel(level)

        if level == MatchLevel.REJECT:
            continue

        if comp.sold_price_aud is None or comp.sold_price_aud <= 0:
            continue

        age_days = _age_days(comp.sold_date, as_of)
        if age_days is None:
            continue

        max_age = (
            settings.exact_comp_max_age_days
            if level in {MatchLevel.EXACT, MatchLevel.STRONG}
            else settings.related_comp_max_age_days
        )

        if age_days > max_age:
            continue

        counts[level] += 1
        accepted.append(
            {
                "price": float(comp.sold_price_aud),
                "age_days": age_days,
                "match_score": float(match.match_score),
                "level": level,
                "sold_date": comp.sold_date,
            }
        )

    exact_records = [
        record
        for record in accepted
        if record["level"] == MatchLevel.EXACT
    ]
    valuation_records = exact_records if exact_records else accepted
    prices = [record["price"] for record in valuation_records]
    filtered_prices = _iqr_filter(prices)
    filtered_records = [
        record
        for record in valuation_records
        if record["price"] in filtered_prices
    ]

    latest_sale = None
    if accepted:
        latest_sale = sorted(
            accepted,
            key=lambda record: record["sold_date"],
            reverse=True,
        )[0]["price"]

    median_sale = _median(filtered_prices)
    weighted_median = _weighted_median(filtered_records)
    trimmed_mean = round(mean(filtered_prices), 2) if filtered_prices else None
    median_30 = _median([record["price"] for record in accepted if record["age_days"] <= 30])
    median_90 = _median([record["price"] for record in accepted if record["age_days"] <= 90])
    median_180 = _median([record["price"] for record in accepted if record["age_days"] <= 180])
    direction, direction_reason = _market_direction(accepted)
    price_spread_pct = _price_spread_pct(filtered_prices)
    mad_pct = _median_absolute_deviation_pct(filtered_prices)
    age_metrics = _age_metrics(filtered_records)

    total_count = len(accepted)
    exact_count = counts[MatchLevel.EXACT]
    strong_count = counts[MatchLevel.STRONG]
    related_count = counts[MatchLevel.RELATED]
    liquidity_score = min(1.0, total_count / 8.0)

    has_high_exact_depth = exact_count >= settings.min_exact_comps_high_confidence
    has_medium_depth = total_count >= settings.min_total_comps_medium_confidence

    if not has_high_exact_depth and not has_medium_depth:
        return SoldValuation(
            source_listing_external_id=source_listing_external_id,
            sold_comp_count=total_count,
            exact_comp_count=exact_count,
            strong_comp_count=strong_count,
            related_comp_count=related_count,
            latest_sale_aud=latest_sale,
            median_sale_aud=median_sale,
            weighted_median_aud=weighted_median,
            trimmed_mean_aud=trimmed_mean,
            median_30_day_aud=median_30,
            median_90_day_aud=median_90,
            median_180_day_aud=median_180,
            liquidity_score=round(liquidity_score, 3),
            comp_confidence=0.0,
            market_direction=direction,
            market_direction_reason=direction_reason,
            status="INSUFFICIENT_SOLD_COMPS",
            explanation={
                "reason": "minimum sold comp depth not met",
                "valuation_records": len(valuation_records),
                "outlier_filtered_count": len(prices) - len(filtered_prices),
                "price_spread_pct": price_spread_pct,
                "median_absolute_deviation_pct": mad_pct,
                **age_metrics,
            },
        )

    average_similarity = (
        sum(record["match_score"] for record in accepted) / total_count
        if total_count
        else 0.0
    )
    exact_bonus = 0.20 if exact_count else 0.0
    comp_confidence = min(
        1.0,
        0.50 * average_similarity
        + 0.30 * liquidity_score
        + exact_bonus,
    )
    dispersion_penalty = 0.0
    if price_spread_pct is not None:
        if price_spread_pct >= 100.0:
            dispersion_penalty = 0.15
        elif price_spread_pct >= 60.0:
            dispersion_penalty = 0.10
        elif price_spread_pct >= 35.0:
            dispersion_penalty = 0.05

    comp_confidence = max(
        0.0,
        comp_confidence - dispersion_penalty,
    )
    fair_value = weighted_median or median_sale
    quick_sale = (
        round(fair_value * settings.quick_sale_discount, 2)
        if fair_value is not None
        else None
    )

    return SoldValuation(
        source_listing_external_id=source_listing_external_id,
        sold_comp_count=total_count,
        exact_comp_count=exact_count,
        strong_comp_count=strong_count,
        related_comp_count=related_count,
        latest_sale_aud=latest_sale,
        median_sale_aud=median_sale,
        weighted_median_aud=weighted_median,
        trimmed_mean_aud=trimmed_mean,
        median_30_day_aud=median_30,
        median_90_day_aud=median_90,
        median_180_day_aud=median_180,
        fair_value_aud=fair_value,
        quick_sale_value_aud=quick_sale,
        liquidity_score=round(liquidity_score, 3),
        comp_confidence=round(comp_confidence, 3),
        market_direction=direction,
        market_direction_reason=direction_reason,
        status="VALUED",
        explanation={
            "basis": "exact comps preferred" if exact_records else "strong/related comps",
            "valuation_records": len(valuation_records),
            "outlier_filtered_count": len(prices) - len(filtered_prices),
            "price_spread_pct": price_spread_pct,
            "median_absolute_deviation_pct": mad_pct,
            **age_metrics,
            "dispersion_confidence_penalty": dispersion_penalty,
            "quick_sale_discount": settings.quick_sale_discount,
        },
    )
