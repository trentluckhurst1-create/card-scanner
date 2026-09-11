from __future__ import annotations

import re
from collections import defaultdict
from statistics import median
from typing import Any, Iterable


PRICING_BASIS = "ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE"
EXACT_MATCH = "EXACT_CARD"
SAME_PRODUCT_VARIANTS = "SAME_PRODUCT_VARIANTS"
PLAYER_YEAR_MARKET = "PLAYER_YEAR_MARKET"


def _norm(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).casefold().strip()
    return re.sub(r"[^a-z0-9]+", "", text)


def _money(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


def _exact_key(card: dict[str, Any]) -> str | None:
    family = card.get("card_family") or {}
    key = family.get("key")
    return str(key) if key else None


def _same_product_key(card: dict[str, Any]) -> str | None:
    identity = card.get("identity") or {}
    sport = _norm(card.get("sport"))
    player = _norm(identity.get("player"))
    year = _norm(identity.get("year"))
    product = _norm(identity.get("set_name") or identity.get("brand"))
    if not sport or not player or not year or not product:
        return None
    return "|".join((sport, player, year, product))


def _player_year_key(card: dict[str, Any]) -> str | None:
    identity = card.get("identity") or {}
    sport = _norm(card.get("sport"))
    player = _norm(identity.get("player"))
    year = _norm(identity.get("year"))
    if not sport or not player or not year:
        return None
    return "|".join((sport, player, year))


def _listing_payload(card: dict[str, Any]) -> dict[str, Any]:
    identity = card.get("identity") or {}
    return {
        "source": card.get("source"),
        "external_id": card.get("external_id"),
        "url": card.get("url"),
        "title": card.get("title"),
        "landed_aud": _money(card.get("landed_aud")),
        "asking_price": _money(card.get("asking_price")),
        "shipping": _money(card.get("shipping")),
        "currency": card.get("currency"),
        "card_number": identity.get("card_number"),
        "parallel": identity.get("parallel"),
        "serial_total": identity.get("serial_total"),
        "grader": identity.get("grader"),
        "grade": identity.get("grade"),
        "rookie": identity.get("rookie"),
        "autograph": identity.get("autograph"),
        "memorabilia": identity.get("memorabilia"),
    }


def _comparison_payload(
    rows: list[dict[str, Any]],
    *,
    comparison_type: str,
    comparison_key: str,
) -> dict[str, Any] | None:
    stores = sorted({str(row.get("source")) for row in rows if row.get("source")})
    if len(stores) < 2:
        return None

    listings = [_listing_payload(row) for row in rows]
    priced = [row for row in listings if row.get("landed_aud") is not None]
    priced.sort(key=lambda row: (float(row["landed_aud"]), str(row.get("source") or "")))

    if not priced:
        return None

    prices = [float(row["landed_aud"]) for row in priced]
    cheapest = priced[0]
    next_best = priced[1] if len(priced) >= 2 else None
    lowest = prices[0]
    highest = prices[-1]
    med = float(median(prices))

    next_best_price = float(next_best["landed_aud"]) if next_best else None
    saving_vs_next = (
        round(next_best_price - lowest, 2)
        if next_best_price is not None
        else None
    )
    saving_vs_median = round(med - lowest, 2)
    saving_vs_highest = round(highest - lowest, 2)

    representative = rows[0]
    identity = representative.get("identity") or {}

    exact_equivalent = comparison_type == EXACT_MATCH

    return {
        "comparison_key": comparison_key,
        "comparison_type": comparison_type,
        "exact_equivalent": exact_equivalent,
        "pricing_basis": PRICING_BASIS,
        "comparison_warning": (
            None
            if exact_equivalent
            else "RELATED ACTIVE LISTINGS ARE NOT GUARANTEED TO BE THE SAME CARD VARIANT"
        ),
        "sport": representative.get("sport"),
        "player": identity.get("player"),
        "year": identity.get("year"),
        "product": identity.get("set_name") or identity.get("brand"),
        "store_count": len(stores),
        "listing_count": len(listings),
        "stores": stores,
        "lowest_active_ask_aud": round(lowest, 2),
        "median_active_ask_aud": round(med, 2),
        "highest_active_ask_aud": round(highest, 2),
        "spread_aud": round(highest - lowest, 2),
        "spread_pct": _pct(highest - lowest, lowest),
        "cheapest_store": cheapest.get("source"),
        "cheapest_external_id": cheapest.get("external_id"),
        "cheapest_url": cheapest.get("url"),
        "cheapest_landed_aud": cheapest.get("landed_aud"),
        "next_best_store": next_best.get("source") if next_best else None,
        "next_best_landed_aud": next_best.get("landed_aud") if next_best else None,
        "saving_vs_next_best_aud": saving_vs_next,
        "saving_vs_next_best_pct": _pct(saving_vs_next, next_best_price),
        "saving_vs_median_aud": saving_vs_median,
        "saving_vs_median_pct": _pct(saving_vs_median, med),
        "saving_vs_highest_aud": saving_vs_highest,
        "saving_vs_highest_pct": _pct(saving_vs_highest, highest),
        "listings": sorted(
            listings,
            key=lambda row: (
                row.get("landed_aud") is None,
                row.get("landed_aud") if row.get("landed_aud") is not None else 0,
                str(row.get("source") or ""),
            ),
        ),
    }


def _group(
    cards: Iterable[dict[str, Any]],
    key_func,
    comparison_type: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        key = key_func(card)
        if key:
            grouped[key].append(card)

    output: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        payload = _comparison_payload(
            rows,
            comparison_type=comparison_type,
            comparison_key=key,
        )
        if payload:
            output.append(payload)

    return output


def build_active_price_comparisons(
    cards: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    rows = list(cards)

    exact = _group(rows, _exact_key, EXACT_MATCH)
    exact_member_ids = {
        (listing.get("source"), listing.get("external_id"))
        for comparison in exact
        for listing in comparison["listings"]
    }

    same_product_candidates = [
        row
        for row in rows
        if (row.get("source"), row.get("external_id")) not in exact_member_ids
    ]
    same_product = _group(
        same_product_candidates,
        _same_product_key,
        SAME_PRODUCT_VARIANTS,
    )

    represented_ids = exact_member_ids | {
        (listing.get("source"), listing.get("external_id"))
        for comparison in same_product
        for listing in comparison["listings"]
    }
    player_year_candidates = [
        row
        for row in rows
        if (row.get("source"), row.get("external_id")) not in represented_ids
    ]
    player_year = _group(
        player_year_candidates,
        _player_year_key,
        PLAYER_YEAR_MARKET,
    )

    all_groups = [*exact, *same_product, *player_year]
    rank = {
        EXACT_MATCH: 0,
        SAME_PRODUCT_VARIANTS: 1,
        PLAYER_YEAR_MARKET: 2,
    }
    all_groups.sort(
        key=lambda row: (
            rank.get(str(row.get("comparison_type")), 9),
            -int(row.get("store_count") or 0),
            -float(row.get("saving_vs_highest_aud") or 0.0),
            str(row.get("player") or ""),
        )
    )

    return {
        "pricing_basis": PRICING_BASIS,
        "governance": {
            "active_asks_are_fair_value": False,
            "related_variants_are_exact_equivalents": False,
            "can_create_buy": False,
        },
        "exact_match_count": len(exact),
        "same_product_variant_count": len(same_product),
        "player_year_market_count": len(player_year),
        "comparison_group_count": len(all_groups),
        "groups": all_groups,
    }
