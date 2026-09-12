from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

FIELDS = (
    "player",
    "year",
    "brand",
    "set_name",
    "card_number",
    "parallel",
    "serial_total",
    "grader",
    "grade",
)


def present(value: object) -> bool:
    return value is not None and str(value).strip() != ""


def exact_ready(card: dict) -> bool:
    family = card.get("card_family") or {}
    if family.get("eligible") is True:
        return True
    identity = card.get("identity") or {}
    base = all(present(identity.get(key)) for key in ("player", "year", "brand", "set_name"))
    if not base:
        return False
    has_number = present(identity.get("card_number"))
    has_named_numbered_parallel = present(identity.get("parallel")) and present(identity.get("serial_total"))
    return has_number or has_named_numbered_parallel


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit NFL staging identity readiness by source.")
    parser.add_argument("--feed", default="docs/nfl_inventory.json")
    parser.add_argument("--output", default="artifacts/nfl_identity_readiness_audit.json")
    args = parser.parse_args()

    feed = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    cards = [card for card in feed.get("market_cards", []) if str(card.get("sport") or "").upper() == "NFL"]

    by_source: dict[str, dict[str, int]] = defaultdict(lambda: {"cards": 0, "exact_ready": 0, **{field: 0 for field in FIELDS}})
    totals = {"cards": 0, "exact_ready": 0, **{field: 0 for field in FIELDS}}

    for card in cards:
        source = str(card.get("source") or "UNKNOWN")
        identity = card.get("identity") or {}
        for bucket in (by_source[source], totals):
            bucket["cards"] += 1
            if exact_ready(card):
                bucket["exact_ready"] += 1
            for field in FIELDS:
                if present(identity.get(field)):
                    bucket[field] += 1

    def decorate(row: dict[str, int]) -> dict:
        cards_n = row["cards"]
        result = dict(row)
        result["coverage_pct"] = {
            key: round((value / cards_n * 100.0), 2) if cards_n else 0.0
            for key, value in row.items()
            if key != "cards"
        }
        return result

    payload = {
        "feed": args.feed,
        "nfl_cards": len(cards),
        "totals": decorate(totals),
        "by_source": {name: decorate(row) for name, row in sorted(by_source.items())},
        "governance": {
            "audit_only": True,
            "matching_rules_changed": False,
            "production_comparison_feed_mutated": False,
        },
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print("NFL_IDENTITY_READINESS_AUDIT=PASS")
    print(f"NFL_CARDS={len(cards)}")
    print(f"NFL_EXACT_READY={totals['exact_ready']}")
    print(f"NFL_EXACT_READY_PCT={payload['totals']['coverage_pct']['exact_ready']:.2f}")
    for source, row in payload["by_source"].items():
        pct = row["coverage_pct"]
        print(
            f"SOURCE={source} CARDS={row['cards']} EXACT_READY={row['exact_ready']} "
            f"EXACT_READY_PCT={pct['exact_ready']:.2f} CARD_NUMBER_PCT={pct['card_number']:.2f} "
            f"PARALLEL_PCT={pct['parallel']:.2f} YEAR_PCT={pct['year']:.2f} "
            f"BRAND_PCT={pct['brand']:.2f} SET_PCT={pct['set_name']:.2f}"
        )
    print("PRODUCTION_COMPARISON_FEED_MUTATED=NO")
    print(f"OUTPUT={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
