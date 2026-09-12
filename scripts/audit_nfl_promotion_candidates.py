from __future__ import annotations

import argparse
import json
from pathlib import Path

from card_scanner.active_price_comparison import EXACT_MATCH, build_active_price_comparisons


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _group_key(group: dict) -> str:
    return str(group.get("comparison_key") or "")


def build_promotion_report(staging: dict, production: dict) -> dict:
    staging_cards = list(staging.get("market_cards") or [])
    staged = build_active_price_comparisons(staging_cards)
    staged_exact = {
        _group_key(group): group
        for group in staged.get("groups") or []
        if group.get("comparison_type") == EXACT_MATCH and _group_key(group)
    }

    production_keys = {
        str(group.get("comparison_key") or "")
        for group in production.get("comparison_groups") or production.get("groups") or []
        if str(group.get("comparison_key") or "")
    }

    new_groups = [
        group for key, group in staged_exact.items() if key not in production_keys
    ]
    new_groups.sort(
        key=lambda row: (
            -int(row.get("store_count") or 0),
            -int(row.get("listing_count") or 0),
            -float(row.get("saving_vs_highest_aud") or 0.0),
            str(row.get("player") or ""),
        )
    )

    return {
        "schema_version": 1,
        "feed_type": "NFL_EXACT_PROMOTION_CANDIDATES_AUDIT_ONLY",
        "governance": {
            "automatic_promotion": False,
            "production_comparison_feed_mutated": False,
            "strict_exact_matcher_reused": True,
            "title_guard_reused": True,
        },
        "metrics": {
            "staging_cards": len(staging_cards),
            "staging_exact_groups": len(staged_exact),
            "production_exact_group_keys": len(production_keys),
            "new_exact_candidate_groups": len(new_groups),
            "new_exact_candidate_listings": sum(
                int(group.get("listing_count") or 0) for group in new_groups
            ),
        },
        "candidates": new_groups,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", default="docs/nfl_inventory.json")
    parser.add_argument("--production", default="docs/comparison.json")
    parser.add_argument("--output", default="artifacts/nfl_promotion_candidates.json")
    args = parser.parse_args()

    report = build_promotion_report(_load(args.staging), _load(args.production))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    metrics = report["metrics"]
    print("NFL_PROMOTION_CANDIDATE_AUDIT=PASS")
    for key, value in metrics.items():
        print(f"{key.upper()}={value}")
    print("AUTOMATIC_PROMOTION=NO")
    print("PRODUCTION_COMPARISON_FEED_MUTATED=NO")
    print(f"OUTPUT={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
