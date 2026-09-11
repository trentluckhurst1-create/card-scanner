from __future__ import annotations

import argparse
import json
from pathlib import Path

from card_scanner.active_price_comparison import build_active_price_comparisons
from card_scanner.dashboard_export import market_listing_to_dashboard_record
from card_scanner.identity_match import canonical_exact_components, exact_components_eligible
from card_scanner.market_catalogue import MarketListingObservation
from card_scanner.models import CardIdentity, Listing
from card_scanner.sources.ebay import EbaySource


def _text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _candidate_targets(cards: list[dict], max_targets: int) -> list[tuple[str, str, str]]:
    ranked: dict[tuple[str, str, str], int] = {}
    labels: dict[tuple[str, str, str], str] = {}

    for card in cards:
        identity = card.get("identity") or {}
        player = str(identity.get("player") or "").strip()
        year = str(identity.get("year") or "").strip()
        sport = str(card.get("sport") or "").upper()
        if not player or not year or not sport:
            continue
        components = canonical_exact_components(sport=sport, identity=identity)
        if not exact_components_eligible(components):
            continue
        key = (sport, _text(player), year)
        ranked[key] = ranked.get(key, 0) + 1
        labels[key] = player

    keys = sorted(ranked, key=lambda key: (-ranked[key], key[0], labels[key].casefold(), key[2]))
    return [(sport, labels[(sport, player_key, year)], year) for sport, player_key, year in keys[:max_targets]]


def _listing_from_record(card: dict) -> Listing:
    identity_payload = card.get("identity") or None
    identity = CardIdentity(**identity_payload) if identity_payload else None
    return Listing(
        source=str(card.get("source") or ""),
        external_id=str(card.get("external_id") or ""),
        url=str(card.get("url") or ""),
        title=str(card.get("title") or ""),
        sport=str(card.get("sport") or ""),
        price=float(card.get("asking_price") if card.get("asking_price") is not None else card.get("price") or 0.0),
        currency=str(card.get("currency") or "AUD"),
        shipping=float(card.get("shipping") or 0.0),
        image_url=card.get("image_url"),
        seller=card.get("seller"),
        condition=card.get("condition"),
        identity=identity,
    )


def enrich_payload(payload: dict, *, max_targets: int = 24, results_per_target: int = 50) -> dict:
    cards = list(payload.get("market_cards") or [])
    ebay = EbaySource()
    missing = ebay.missing_credentials()
    metrics = dict(payload.get("metrics") or {})

    metrics.update({
        "ebay_enabled": not bool(missing),
        "ebay_targets": 0,
        "ebay_queries": 0,
        "ebay_added_cards": 0,
        "ebay_errors": 0,
    })

    if missing:
        payload["metrics"] = metrics
        payload["ebay_status"] = "DISABLED_MISSING_CREDENTIALS"
        payload["ebay_missing_credentials"] = missing
        return payload

    targets = _candidate_targets(cards, max_targets=max_targets)
    metrics["ebay_targets"] = len(targets)
    seen = {(str(card.get("source") or "").casefold(), str(card.get("external_id") or "")) for card in cards}
    errors: list[str] = []

    for sport, player, year in targets:
        metrics["ebay_queries"] += 1
        try:
            found = ebay.search(sport=sport, query=f"{year} {player}", limit=max(1, int(results_per_target)))
        except Exception as exc:
            errors.append(f"{sport}: {player}: {type(exc).__name__}: {exc}")
            continue

        for row in found:
            identity = row.identity
            if identity is None:
                continue
            if _text(identity.player) != _text(player):
                continue
            if str(identity.year or "").strip() != year:
                continue
            key = (str(row.source).casefold(), str(row.external_id))
            if key in seen:
                continue
            seen.add(key)
            cards.append(market_listing_to_dashboard_record(MarketListingObservation(listing=row)))
            metrics["ebay_added_cards"] += 1

    metrics["ebay_errors"] = len(errors)
    metrics["active_cards"] = len(cards)
    payload["market_cards"] = cards
    payload["metrics"] = metrics
    payload["ebay_status"] = "ENABLED"
    payload["ebay_errors"] = errors

    by_source: dict[str, int] = {}
    by_sport: dict[str, int] = {}
    for card in cards:
        source = str(card.get("source") or "UNKNOWN")
        sport = str(card.get("sport") or "UNKNOWN")
        by_source[source] = by_source.get(source, 0) + 1
        by_sport[sport] = by_sport.get(sport, 0) + 1
    payload["by_source"] = dict(sorted(by_source.items()))
    payload["by_sport"] = dict(sorted(by_sport.items()))

    comparisons = build_active_price_comparisons(cards)
    payload["active_price_comparisons"] = comparisons
    metrics["comparison_groups"] = comparisons["comparison_group_count"]
    metrics["exact_matches"] = comparisons["exact_match_count"]
    metrics["same_product_variants"] = comparisons["same_product_variant_count"]
    metrics["player_year_markets"] = comparisons["player_year_market_count"]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Targeted eBay Browse API enrichment for active market feed.")
    parser.add_argument("--feed", default="docs/active_market.json")
    parser.add_argument("--max-targets", type=int, default=24)
    parser.add_argument("--results-per-target", type=int, default=50)
    args = parser.parse_args()

    feed = Path(args.feed)
    payload = json.loads(feed.read_text(encoding="utf-8"))
    payload = enrich_payload(payload, max_targets=max(0, args.max_targets), results_per_target=max(1, args.results_per_target))
    feed.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics = payload.get("metrics") or {}
    print(f"EBAY_STATUS={payload.get('ebay_status')}")
    print(f"EBAY_TARGETS={metrics.get('ebay_targets', 0)}")
    print(f"EBAY_QUERIES={metrics.get('ebay_queries', 0)}")
    print(f"EBAY_ADDED_CARDS={metrics.get('ebay_added_cards', 0)}")
    print(f"EBAY_ERRORS={metrics.get('ebay_errors', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
