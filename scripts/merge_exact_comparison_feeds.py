from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _group_key(group: dict[str, Any]) -> str:
    return str(group.get("comparison_key") or "")


def _listing_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("source") or "").casefold(), str(row.get("external_id") or ""))


def merge_refresh_preserving_live(
    previous: dict[str, Any], fresh: dict[str, Any]
) -> dict[str, Any]:
    """Refresh exact groups additively without allowing transient deletion.

    Fresh groups replace prior groups on the same comparison key so prices can
    update. Prior groups absent from the fresh crawl remain live rather than
    disappearing because a store timed out or rate-limited the refresh.
    """
    previous_groups = list(previous.get("comparison_groups") or previous.get("groups") or [])
    fresh_groups = list(fresh.get("comparison_groups") or fresh.get("groups") or [])

    merged_by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for group in previous_groups:
        key = _group_key(group)
        if not key:
            continue
        if key not in merged_by_key:
            order.append(key)
        merged_by_key[key] = group

    fresh_keys: set[str] = set()
    for group in fresh_groups:
        key = _group_key(group)
        if not key:
            continue
        fresh_keys.add(key)
        if key not in merged_by_key:
            order.append(key)
        merged_by_key[key] = group

    final_groups = [merged_by_key[key] for key in order]
    retained_keys = {
        key for key in merged_by_key if key not in fresh_keys
    }

    wanted_listing_keys = {
        _listing_key(listing)
        for group in final_groups
        for listing in (group.get("listings") or [])
        if all(_listing_key(listing))
    }

    cards: dict[tuple[str, str], dict[str, Any]] = {}
    for card in previous.get("market_cards") or []:
        key = _listing_key(card)
        if key in wanted_listing_keys:
            cards[key] = card
    for card in fresh.get("market_cards") or []:
        key = _listing_key(card)
        if key in wanted_listing_keys:
            cards[key] = card

    output = dict(fresh)
    output["feed_type"] = "EXACT_CARD_STORE_COMPARISON_ONLY"
    output["comparison_groups"] = final_groups
    output["market_cards"] = list(cards.values())

    governance = dict(output.get("governance") or {})
    governance.update(
        {
            "exact_card_only": True,
            "refresh_is_additive": True,
            "fresh_groups_replace_same_key": True,
            "transient_refresh_group_deletion_allowed": False,
        }
    )
    output["governance"] = governance

    listing_count = sum(
        int(group.get("listing_count") or len(group.get("listings") or []))
        for group in final_groups
    )
    metrics = dict(output.get("metrics") or {})
    metrics.update(
        {
            "previous_exact_groups": len(previous_groups),
            "fresh_exact_groups": len(fresh_groups),
            "retained_previous_groups_missing_from_fresh": len(retained_keys),
            "exact_comparison_groups": len(final_groups),
            "exact_comparison_listings": listing_count,
            "previous_groups_lost": 0,
        }
    )
    output["metrics"] = metrics
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Preserve live exact-card comparison groups across transient refresh gaps.")
    parser.add_argument("--previous", required=True)
    parser.add_argument("--fresh", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    merged = merge_refresh_preserving_live(_load(args.previous), _load(args.fresh))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics = merged["metrics"]
    print("EXACT_COMPARISON_REFRESH_GUARD=PASS")
    print(f"PREVIOUS_EXACT_GROUPS={metrics['previous_exact_groups']}")
    print(f"FRESH_EXACT_GROUPS={metrics['fresh_exact_groups']}")
    print(f"RETAINED_MISSING_FROM_FRESH={metrics['retained_previous_groups_missing_from_fresh']}")
    print(f"FINAL_EXACT_GROUPS={metrics['exact_comparison_groups']}")
    print("PREVIOUS_GROUPS_LOST=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
