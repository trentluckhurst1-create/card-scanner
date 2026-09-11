from __future__ import annotations

import re
from collections import defaultdict
from statistics import median
from typing import Any, Iterable

from .identity_match import norm_token, normalize_product


PRICING_BASIS = "ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE"
EXACT_MATCH = "EXACT_CARD"
SAME_PRODUCT_VARIANTS = "SAME_PRODUCT_VARIANTS"
PLAYER_YEAR_MARKET = "PLAYER_YEAR_MARKET"

# Extra title-level discriminators used only as a rejection guard. These never
# create an exact match; they can only split an otherwise exact structured group.
# This is deliberately conservative because false exact-card comparisons are
# worse than missing a comparison.
TITLE_VARIANT_PHRASES = (
    "choice dragon",
    "choice red",
    "choice blue",
    "choice green",
    "choice black",
    "choice gold",
    "neon blue",
    "neon green",
    "neon orange",
    "neon pink",
    "neon purple",
    "press proof red",
    "press proof blue",
    "reactive orange",
    "reactive blue",
    "reactive green",
    "red white blue",
    "cracked ice",
    "gold vinyl",
    "gold wave",
    "silver wave",
    "blue wave",
    "red wave",
    "green wave",
    "purple wave",
    "orange wave",
    "gold shimmer",
    "silver shimmer",
    "blue shimmer",
    "red shimmer",
    "green shimmer",
    "purple shimmer",
    "gold refractor",
    "silver refractor",
    "blue refractor",
    "red refractor",
    "green refractor",
    "purple refractor",
    "orange refractor",
    "superfractor",
    "x-fractor",
    "black pearl",
    "stained glass",
    "pink laser",
    "pink lazer",
    "green velocity",
    "teal explosion",
    "purple ice",
    "blue ice",
    "gold disco",
    "gold foil",
    "silver prizm",
    "black prizm",
    "aqua reptilian",
    "choice dragon",
)

SINGLE_VARIANT_WORDS = {
    "dragon",
    "disco",
    "holo",
    "mojo",
    "pulsar",
    "scope",
    "sparkle",
    "shimmer",
    "superfractor",
}


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
    sport = norm_token(card.get("sport"))
    player = norm_token(identity.get("player"))
    year = norm_token(identity.get("year"))
    brand, product = normalize_product(
        brand=identity.get("brand"),
        set_name=identity.get("set_name"),
    )
    if not sport or not player or not year or not brand or not product:
        return None
    return "|".join((sport, player, year, brand, product))


def _player_year_key(card: dict[str, Any]) -> str | None:
    identity = card.get("identity") or {}
    sport = norm_token(card.get("sport"))
    player = norm_token(identity.get("player"))
    year = norm_token(identity.get("year"))
    if not sport or not player or not year:
        return None
    return "|".join((sport, player, year))


def _title_guard_signature(card: dict[str, Any]) -> str:
    """Return conservative title discriminators that can reject a false match.

    The structured identity remains the primary matcher. This guard captures
    information title parsing may have missed, such as "Choice Dragon" or a bare
    card number written as "Spectra 125" rather than "#125".
    """
    title = str(card.get("title") or "")
    lower = " ".join(title.casefold().split())
    identity = card.get("identity") or {}

    phrases = [phrase for phrase in TITLE_VARIANT_PHRASES if phrase in lower]
    words = set(re.findall(r"[a-z]+", lower))
    phrases.extend(sorted(word for word in SINGLE_VARIANT_WORDS if word in words))

    # Remove numbers already explained by known identity fields before looking
    # for an otherwise-unparsed bare set/card number.
    scrubbed = lower
    year = str(identity.get("year") or "").strip().casefold()
    if year:
        scrubbed = scrubbed.replace(year, " ")
    scrubbed = re.sub(r"\b(?:psa|bgs|sgc|cgc)\s*\d+(?:\.\d+)?\b", " ", scrubbed)
    scrubbed = re.sub(r"\b\d{1,4}\s*/\s*\d{1,4}\b", " ", scrubbed)
    scrubbed = re.sub(r"#\s*[a-z0-9][a-z0-9.\-]*", " ", scrubbed)
    scrubbed = re.sub(r"\(\s*\d+\s*\)", " ", scrubbed)
    bare_numbers = [
        str(int(value))
        for value in re.findall(r"(?<![a-z0-9])([0-9]{1,3})(?![a-z0-9])", scrubbed)
        if int(value) > 0
    ]

    # Do not duplicate a parsed card number in the guard.
    parsed_card = str(identity.get("card_number") or "").strip().lstrip("#")
    if parsed_card.isdigit():
        bare_numbers = [value for value in bare_numbers if value != str(int(parsed_card))]

    tokens = sorted(set(norm_token(value) for value in [*phrases, *bare_numbers] if value))
    return ",".join(tokens)


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
        "title_guard": _title_guard_signature(card),
    }


def _match_explanation(
    rows: list[dict[str, Any]], comparison_type: str
) -> tuple[float, list[str]]:
    if comparison_type == EXACT_MATCH:
        family = rows[0].get("card_family") or {}
        reasons = list(
            family.get("match_reasons")
            or ["same strict canonical card identity"]
        )
        reasons.append("title discriminator guard passed")
        return float(family.get("match_confidence") or 1.0), reasons
    if comparison_type == SAME_PRODUCT_VARIANTS:
        return 0.65, [
            "same player",
            "same year",
            "same brand/product",
            "variant fields may differ",
        ]
    return 0.35, ["same player", "same year", "product and variant may differ"]


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
    priced.sort(
        key=lambda row: (float(row["landed_aud"]), str(row.get("source") or ""))
    )
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
        round(next_best_price - lowest, 2) if next_best_price is not None else None
    )
    saving_vs_median = round(med - lowest, 2)
    saving_vs_highest = round(highest - lowest, 2)

    representative = rows[0]
    identity = representative.get("identity") or {}
    exact_equivalent = comparison_type == EXACT_MATCH
    confidence, reasons = _match_explanation(rows, comparison_type)

    return {
        "comparison_key": comparison_key,
        "comparison_type": comparison_type,
        "exact_equivalent": exact_equivalent,
        "match_confidence": round(confidence, 2),
        "match_reasons": reasons,
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
    cards: Iterable[dict[str, Any]], key_func, comparison_type: str
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        key = key_func(card)
        if key:
            if comparison_type == EXACT_MATCH:
                # Structured identity creates the candidate group; title-level
                # evidence can only split it. A title mismatch can never be
                # overridden merely to increase comparison counts.
                key = f"{key}|tg:{_title_guard_signature(card)}"
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


def build_active_price_comparisons(cards: Iterable[dict[str, Any]]) -> dict[str, Any]:
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
    rank = {EXACT_MATCH: 0, SAME_PRODUCT_VARIANTS: 1, PLAYER_YEAR_MARKET: 2}
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
            "title_discriminator_guard_required_for_exact": True,
            "can_create_buy": False,
        },
        "exact_match_count": len(exact),
        "same_product_variant_count": len(same_product),
        "player_year_market_count": len(player_year),
        "comparison_group_count": len(all_groups),
        "groups": all_groups,
    }
