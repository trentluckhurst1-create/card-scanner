from __future__ import annotations

import argparse
import json
from pathlib import Path

from card_scanner.active_price_comparison import build_active_price_comparisons
from card_scanner.identity_match import (
    canonical_exact_components,
    exact_components_eligible,
)
from card_scanner.opportunity_scanner import MultiStoreSource

from publish_active_market import (
    _dedupe,
    build_active_market_payload,
    cloud_active_store_source,
)


def _source(value: object) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _exact_identity_ready(card: dict) -> bool:
    identity = card.get("identity") or {}
    sport = str(card.get("sport") or "").upper().strip()
    components = canonical_exact_components(sport=sport, identity=identity)
    return exact_components_eligible(components)


def retain_prior_ebay_cards(
    output: Path,
    *,
    max_retain_cycles: int,
) -> tuple[list[dict], int]:
    """Carry recent, exact-eligible staged eBay matches into the next crawl.

    The NFL retailer inventory is refreshed from scratch every run. Without this
    carry-forward, the eBay enrichment step repeatedly spends its API allowance
    on the same first batch of card identities. Retained eBay rows allow the
    next enrichment pass to skip signatures already covered and move deeper into
    the uncovered NFL catalogue.

    Rows expire after a small number of scheduled cycles so eBay availability is
    periodically revalidated instead of being treated as permanently live.
    """
    if not output.exists() or max_retain_cycles <= 0:
        return [], 0

    try:
        prior = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], 0

    if prior.get("feed_type") != "NFL_DEEP_INVENTORY_STAGING":
        return [], 0

    retained: list[dict] = []
    expired = 0
    seen: set[tuple[str, str]] = set()
    for card in prior.get("market_cards") or []:
        if _source(card.get("source")) != "ebay":
            continue
        if str(card.get("sport") or "").upper().strip() != "NFL":
            continue
        if not _exact_identity_ready(card):
            continue

        try:
            cycles = int(card.get("staging_ebay_retain_cycles") or 0)
        except (TypeError, ValueError):
            cycles = 0
        if cycles >= max_retain_cycles:
            expired += 1
            continue

        key = (_source(card.get("source")), str(card.get("external_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        row = dict(card)
        row["staging_ebay_retain_cycles"] = cycles + 1
        retained.append(row)

    return retained, expired


def _merge_retained_ebay(payload: dict, retained: list[dict], *, expired: int) -> dict:
    cards = list(payload.get("market_cards") or [])
    seen = {
        (_source(card.get("source")), str(card.get("external_id") or ""))
        for card in cards
    }
    added = 0
    for card in retained:
        key = (_source(card.get("source")), str(card.get("external_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        cards.append(card)
        added += 1

    payload["market_cards"] = cards
    metrics = dict(payload.get("metrics") or {})
    metrics["retained_ebay_cards"] = added
    metrics["expired_ebay_cards"] = expired
    metrics["active_cards"] = len(cards)

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
    payload["metrics"] = metrics
    return payload


def collect_nfl_inventory(
    source: MultiStoreSource,
    *,
    limit_per_store: int,
):
    result = source.collect(
        sport="NFL",
        query="",
        limit=max(1, int(limit_per_store)),
    )
    listings = _dedupe(result.listings)
    errors = [f"NFL: {message}" for message in result.store_errors]
    searched_store_names = {str(listing.source) for listing in listings}
    stores_searched = max(result.stores_searched, len(searched_store_names))
    return listings, result.stores_considered, stores_searched, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Publish a deep NFL-only staging inventory without mutating the "
            "production exact-card comparison feed."
        )
    )
    parser.add_argument("--limit-per-store", type=int, default=2500)
    parser.add_argument("--ebay-retain-cycles", type=int, default=3)
    parser.add_argument("--output", default="docs/nfl_inventory.json")
    args = parser.parse_args()

    output = Path(args.output)
    retained_ebay, expired_ebay = retain_prior_ebay_cards(
        output,
        max_retain_cycles=max(0, args.ebay_retain_cycles),
    )

    source = cloud_active_store_source()
    listings, stores_considered, stores_searched, errors = collect_nfl_inventory(
        source,
        limit_per_store=max(1, args.limit_per_store),
    )
    payload = build_active_market_payload(
        listings,
        store_errors=errors,
        stores_considered=stores_considered,
        stores_searched=stores_searched,
    )
    payload["feed_type"] = "NFL_DEEP_INVENTORY_STAGING"
    payload["governance"].update(
        {
            "production_comparison_feed_mutated": False,
            "promotion_requires_exact_identity": True,
            "staging_inventory_only": True,
            "verified_ebay_matches_retained_between_runs": True,
            "retained_ebay_matches_expire_for_revalidation": True,
        }
    )
    payload = _merge_retained_ebay(
        payload,
        retained_ebay,
        expired=expired_ebay,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    metrics = payload["metrics"]
    print("CARD_SCANNER_NFL_DEEP_INVENTORY=PASS")
    print(f"NFL_ACTIVE_CARDS={payload['by_sport'].get('NFL', 0)}")
    print(f"STORES_SEARCHED={metrics['stores_searched']}/{metrics['stores_considered']}")
    print(f"STORE_ERRORS={metrics['store_error_count']}")
    print(f"RETAINED_EBAY_CARDS={metrics.get('retained_ebay_cards', 0)}")
    print(f"EXPIRED_EBAY_CARDS={metrics.get('expired_ebay_cards', 0)}")
    print(f"STAGING_COMPARISON_GROUPS={metrics['comparison_groups']}")
    print(f"STAGING_EXACT_MATCHES={metrics['exact_matches']}")
    print("PRODUCTION_COMPARISON_FEED_MUTATED=NO")
    print(f"OUTPUT={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
