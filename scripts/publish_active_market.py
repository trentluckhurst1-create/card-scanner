from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from card_scanner.active_price_comparison import build_active_price_comparisons
from card_scanner.cli import opportunity_store_source
from card_scanner.dashboard_export import market_listing_to_dashboard_record
from card_scanner.market_catalogue import MarketListingObservation
from card_scanner.models import Listing
from card_scanner.opportunity_scanner import SPORTS, MultiStoreSource, NamedStoreSource
from card_scanner.sources.the_hobby import TheHobbySource


ACTIVE_MARKET_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe(listings: Iterable[Listing]) -> list[Listing]:
    output: list[Listing] = []
    seen: set[tuple[str, str]] = set()
    for listing in listings:
        key = (str(listing.source), str(listing.external_id))
        if key in seen:
            continue
        seen.add(key)
        output.append(listing)
    return output


def build_active_market_payload(
    listings: Iterable[Listing],
    *,
    generated_at: str | None = None,
    store_errors: Iterable[str] = (),
    stores_considered: int = 4,
    stores_searched: int = 4,
) -> dict:
    rows = _dedupe(listings)
    errors = tuple(store_errors)
    cards = [
        market_listing_to_dashboard_record(MarketListingObservation(listing=row))
        for row in rows
    ]
    comparisons = build_active_price_comparisons(cards)
    by_source: dict[str, int] = {}
    by_sport: dict[str, int] = {}
    for card in cards:
        source = str(card.get("source") or "UNKNOWN")
        sport = str(card.get("sport") or "UNKNOWN")
        by_source[source] = by_source.get(source, 0) + 1
        by_sport[sport] = by_sport.get(sport, 0) + 1

    return {
        "schema_version": ACTIVE_MARKET_SCHEMA_VERSION,
        "generated_at": generated_at or _now(),
        "feed_type": "ACTIVE_MARKET_COMPARISON_ONLY",
        "pricing_basis": "ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE",
        "governance": {
            "contains_sold_evidence": False,
            "contains_fair_value": False,
            "can_create_buy": False,
            "persistent_history_claimed": False,
        },
        "metrics": {
            "active_cards": len(cards),
            "stores_considered": stores_considered,
            "stores_searched": stores_searched,
            "store_error_count": len(errors),
            "comparison_groups": comparisons["comparison_group_count"],
            "exact_matches": comparisons["exact_match_count"],
            "same_product_variants": comparisons["same_product_variant_count"],
            "player_year_markets": comparisons["player_year_market_count"],
        },
        "by_source": dict(sorted(by_source.items())),
        "by_sport": dict(sorted(by_sport.items())),
        "store_errors": list(errors),
        "market_cards": cards,
        "active_price_comparisons": comparisons,
    }


def cloud_active_store_source() -> MultiStoreSource:
    """Return cloud-safe active acquisition sources without altering local research scope."""
    source, _ = opportunity_store_source("all")
    if not isinstance(source, MultiStoreSource):
        raise RuntimeError("Expected all-store MultiStoreSource")

    return MultiStoreSource([
        *source.stores,
        NamedStoreSource(name="The Hobby", source=TheHobbySource()),
    ])


def collect_active_market(*, limit_per_store_per_sport: int) -> tuple[list[Listing], int, int, list[str]]:
    source = cloud_active_store_source()

    listings: list[Listing] = []
    errors: list[str] = []
    stores_searched_total = 0
    stores_considered_total = 0
    searched_store_names: set[str] = set()

    for sport in SPORTS:
        result = source.collect(sport=sport, query="", limit=limit_per_store_per_sport)
        listings.extend(result.listings)
        errors.extend(f"{sport}: {message}" for message in result.store_errors)
        stores_considered_total = max(stores_considered_total, result.stores_considered)
        for listing in result.listings:
            searched_store_names.add(str(listing.source))
        if result.stores_searched:
            stores_searched_total = max(stores_searched_total, result.stores_searched)

    return _dedupe(listings), stores_considered_total, max(stores_searched_total, len(searched_store_names)), errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a secret-free active-store comparison feed.")
    parser.add_argument("--limit-per-store-per-sport", type=int, default=125)
    parser.add_argument("--output", default="docs/active_market.json")
    args = parser.parse_args()

    listings, stores_considered, stores_searched, errors = collect_active_market(
        limit_per_store_per_sport=max(1, args.limit_per_store_per_sport),
    )
    payload = build_active_market_payload(
        listings,
        store_errors=errors,
        stores_considered=stores_considered,
        stores_searched=stores_searched,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics = payload["metrics"]
    print("CARD_SCANNER_ACTIVE_MARKET_PUBLISH=PASS")
    print(f"ACTIVE_CARDS={metrics['active_cards']}")
    print(f"STORES_SEARCHED={metrics['stores_searched']}/{metrics['stores_considered']}")
    print(f"STORE_ERRORS={metrics['store_error_count']}")
    for source_name, count in payload["by_source"].items():
        safe_source = source_name.upper().replace(" ", "_")
        print(f"ACTIVE_SOURCE_{safe_source}={count}")
    for sport, count in payload["by_sport"].items():
        print(f"ACTIVE_SPORT_{sport.upper()}={count}")
    for index, message in enumerate(payload["store_errors"], start=1):
        print(f"STORE_ERROR_{index}={message}")
    print(f"COMPARISON_GROUPS={metrics['comparison_groups']}")
    print(f"EXACT_MATCHES={metrics['exact_matches']}")
    print(f"SAME_PRODUCT_VARIANTS={metrics['same_product_variants']}")
    print(f"PLAYER_YEAR_MARKETS={metrics['player_year_markets']}")
    print("SOLD_EVIDENCE_INCLUDED=NO")
    print("FAIR_VALUE_INCLUDED=NO")
    print("PERSISTENT_HISTORY_CLAIMED=NO")
    print(f"OUTPUT={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
