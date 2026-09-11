from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXACT_TYPE = "EXACT_CARD"
SCHEMA_VERSION = 1


def build_exact_comparison_feed(payload: dict[str, Any]) -> dict[str, Any]:
    comparisons = payload.get("active_price_comparisons") or {}
    groups = [
        group
        for group in (comparisons.get("groups") or [])
        if group.get("comparison_type") == EXACT_TYPE
        and int(group.get("store_count") or 0) >= 2
    ]

    wanted: set[tuple[str, str]] = set()
    listing_count = 0
    for group in groups:
        for listing in group.get("listings") or []:
            source = str(listing.get("source") or "")
            external_id = str(listing.get("external_id") or "")
            if source and external_id:
                wanted.add((source.casefold(), external_id))
                listing_count += 1

    cards = []
    for card in payload.get("market_cards") or []:
        key = (
            str(card.get("source") or "").casefold(),
            str(card.get("external_id") or ""),
        )
        if key in wanted:
            cards.append(card)

    metrics = payload.get("metrics") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": payload.get("generated_at"),
        "feed_type": "EXACT_CARD_STORE_COMPARISON_ONLY",
        "pricing_basis": "ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE",
        "governance": {
            "exact_card_only": True,
            "related_variants_included": False,
            "player_year_context_included": False,
            "active_asks_are_fair_value": False,
            "can_create_buy": False,
        },
        "metrics": {
            "active_cards_scanned": metrics.get("active_cards", len(payload.get("market_cards") or [])),
            "exact_comparison_groups": len(groups),
            "exact_comparison_listings": listing_count,
        },
        "market_cards": cards,
        "comparison_groups": groups,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish exact-card-only store comparison feed.")
    parser.add_argument("--feed", default="docs/active_market.json")
    parser.add_argument("--output", default="docs/comparison.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    exact = build_exact_comparison_feed(payload)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(exact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("CARD_SCANNER_EXACT_COMPARISON_PUBLISH=PASS")
    print(f"ACTIVE_CARDS_SCANNED={exact['metrics']['active_cards_scanned']}")
    print(f"EXACT_COMPARISON_GROUPS={exact['metrics']['exact_comparison_groups']}")
    print(f"EXACT_COMPARISON_LISTINGS={exact['metrics']['exact_comparison_listings']}")
    print("RELATED_VARIANTS_INCLUDED=NO")
    print("PLAYER_YEAR_CONTEXT_INCLUDED=NO")
    print("ACTIVE_ASKS_ARE_FAIR_VALUE=NO")
    print("EXACT_COMPARISONS_CAN_CREATE_BUY=NO")
    print(f"OUTPUT={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
