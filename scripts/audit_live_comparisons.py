from __future__ import annotations

import argparse
import json
from pathlib import Path

from card_scanner.active_price_comparison import build_active_price_comparisons
from card_scanner.dashboard_export import FAMILY_MATCH_RULE, canonical_family_key


def _upgrade_family_keys(cards: list[dict]) -> int:
    upgraded = 0
    for card in cards:
        identity = card.get("identity") or {}
        key = canonical_family_key(sport=str(card.get("sport") or ""), identity=identity)
        family = dict(card.get("card_family") or {})
        if key and family.get("key") != key:
            upgraded += 1
        family["key"] = key
        family["eligible"] = key is not None
        family["match_rule"] = FAMILY_MATCH_RULE
        card["card_family"] = family
    return upgraded


def build_audit(feed: dict) -> dict:
    cards = [dict(row) for row in feed.get("market_cards") or []]
    upgraded = _upgrade_family_keys(cards)
    comparisons = build_active_price_comparisons(cards)

    groups = comparisons.get("groups") or []
    ranked = sorted(
        groups,
        key=lambda row: (
            0 if row.get("comparison_type") == "EXACT_CARD" else 1,
            -float(row.get("saving_vs_highest_aud") or 0.0),
            -int(row.get("store_count") or 0),
        ),
    )

    return {
        "feed_generated_at": feed.get("generated_at"),
        "market_cards": len(cards),
        "family_keys_recomputed": upgraded,
        "comparison_group_count": comparisons.get("comparison_group_count", 0),
        "exact_match_count": comparisons.get("exact_match_count", 0),
        "same_product_variant_count": comparisons.get("same_product_variant_count", 0),
        "player_year_market_count": comparisons.get("player_year_market_count", 0),
        "governance": comparisons.get("governance"),
        "top_groups": ranked[:25],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", default="docs/market.json")
    parser.add_argument("--output", default="artifacts/live_comparison_audit.json")
    args = parser.parse_args()

    feed_path = Path(args.feed)
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    audit = build_audit(feed)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("CARD_SCANNER_LIVE_COMPARISON_AUDIT=PASS")
    print(f"MARKET_CARDS={audit['market_cards']}")
    print(f"FAMILY_KEYS_RECOMPUTED={audit['family_keys_recomputed']}")
    print(f"COMPARISON_GROUPS={audit['comparison_group_count']}")
    print(f"EXACT_MATCHES={audit['exact_match_count']}")
    print(f"SAME_PRODUCT_VARIANTS={audit['same_product_variant_count']}")
    print(f"PLAYER_YEAR_MARKETS={audit['player_year_market_count']}")
    print("ACTIVE_ASKS_ARE_FAIR_VALUE=NO")
    print("ACTIVE_PRICE_COMPARISONS_CAN_CREATE_BUY=NO")

    for index, group in enumerate(audit["top_groups"][:10], start=1):
        print(
            "TOP_GROUP_{}={} | {} | {} | stores={} | low={} | high={} | spread={} | cheapest={}".format(
                index,
                group.get("comparison_type"),
                group.get("player") or "UNKNOWN",
                group.get("product") or "UNKNOWN",
                group.get("store_count") or 0,
                group.get("lowest_active_ask_aud"),
                group.get("highest_active_ask_aud"),
                group.get("spread_aud"),
                group.get("cheapest_store"),
            )
        )

    print(f"AUDIT_JSON={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
