from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit identity completeness in a published active-market feed.")
    parser.add_argument("--feed", default="docs/active_market.json")
    parser.add_argument("--output", default="artifacts/identity_completeness_audit.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    cards = list(payload.get("market_cards") or [])

    fields = (
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

    overall = Counter()
    by_source: dict[str, Counter] = defaultdict(Counter)
    by_sport: dict[str, Counter] = defaultdict(Counter)

    exact_ready = 0
    product_ready = 0
    player_year_ready = 0

    for card in cards:
        identity = card.get("identity") or {}
        source = str(card.get("source") or "UNKNOWN")
        sport = str(card.get("sport") or "UNKNOWN")

        overall["cards"] += 1
        by_source[source]["cards"] += 1
        by_sport[sport]["cards"] += 1

        for field in fields:
            if present(identity.get(field)):
                overall[f"has_{field}"] += 1
                by_source[source][f"has_{field}"] += 1
                by_sport[sport][f"has_{field}"] += 1
            else:
                overall[f"missing_{field}"] += 1
                by_source[source][f"missing_{field}"] += 1
                by_sport[sport][f"missing_{field}"] += 1

        has_player = present(identity.get("player"))
        has_year = present(identity.get("year"))
        has_product = present(identity.get("brand")) or present(identity.get("set_name"))
        has_discriminator = any(
            present(identity.get(field))
            for field in ("card_number", "parallel", "serial_total")
        )

        if has_player and has_year:
            player_year_ready += 1
        if has_player and has_year and has_product:
            product_ready += 1
        if has_player and has_year and has_product and has_discriminator:
            exact_ready += 1

    def rates(counter: Counter) -> dict:
        total = int(counter.get("cards", 0))
        data = {k: int(v) for k, v in sorted(counter.items())}
        if total:
            for field in fields:
                data[f"{field}_coverage_pct"] = round(counter.get(f"has_{field}", 0) / total * 100, 2)
        return data

    report = {
        "feed_generated_at": payload.get("generated_at"),
        "cards": len(cards),
        "readiness": {
            "player_year_ready": player_year_ready,
            "product_ready": product_ready,
            "exact_ready": exact_ready,
            "player_year_ready_pct": round(player_year_ready / len(cards) * 100, 2) if cards else 0.0,
            "product_ready_pct": round(product_ready / len(cards) * 100, 2) if cards else 0.0,
            "exact_ready_pct": round(exact_ready / len(cards) * 100, 2) if cards else 0.0,
        },
        "overall": rates(overall),
        "by_source": {k: rates(v) for k, v in sorted(by_source.items())},
        "by_sport": {k: rates(v) for k, v in sorted(by_sport.items())},
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("CARD_SCANNER_IDENTITY_COMPLETENESS_AUDIT=PASS")
    print(f"MARKET_CARDS={len(cards)}")
    print(f"PLAYER_YEAR_READY={player_year_ready}")
    print(f"PRODUCT_READY={product_ready}")
    print(f"EXACT_READY={exact_ready}")
    for field in fields:
        print(f"IDENTITY_{field.upper()}_COVERAGE_PCT={report['overall'].get(field + '_coverage_pct', 0.0)}")
    for source, data in report["by_source"].items():
        label = source.upper().replace(" ", "_")
        print(f"SOURCE_{label}_CARDS={data['cards']}")
        print(f"SOURCE_{label}_CARD_NUMBER_COVERAGE_PCT={data.get('card_number_coverage_pct', 0.0)}")
        print(f"SOURCE_{label}_PARALLEL_COVERAGE_PCT={data.get('parallel_coverage_pct', 0.0)}")
    print(f"AUDIT_JSON={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
