from __future__ import annotations

import argparse
import json
from pathlib import Path

from card_scanner.opportunity_scanner import MultiStoreSource

from publish_active_market import (
    _dedupe,
    build_active_market_payload,
    cloud_active_store_source,
)


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
    parser.add_argument("--output", default="docs/nfl_inventory.json")
    args = parser.parse_args()

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
        }
    )

    output = Path(args.output)
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
    print(f"STAGING_COMPARISON_GROUPS={metrics['comparison_groups']}")
    print(f"STAGING_EXACT_MATCHES={metrics['exact_matches']}")
    print("PRODUCTION_COMPARISON_FEED_MUTATED=NO")
    print(f"OUTPUT={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
