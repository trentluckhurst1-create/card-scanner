from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from card_scanner.identity_match import norm_token, normalize_product


def _identity(card: dict[str, Any]) -> dict[str, Any]:
    return card.get("identity") or {}


def _player_year_key(card: dict[str, Any]) -> tuple[str, str, str] | None:
    identity = _identity(card)
    parts = (
        norm_token(card.get("sport")),
        norm_token(identity.get("player")),
        norm_token(identity.get("year")),
    )
    return parts if all(parts) else None


def _product_key(card: dict[str, Any]) -> tuple[str, str] | None:
    identity = _identity(card)
    brand, product = normalize_product(
        brand=identity.get("brand"),
        set_name=identity.get("set_name"),
    )
    return (brand, product) if brand and product else None


def _norm_card_number(value: Any) -> str:
    token = norm_token(value)
    if token.isdigit():
        return str(int(token))
    return token


def _norm_grade(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        number = float(value)
        return str(int(number)) if number.is_integer() else str(number)
    except (TypeError, ValueError):
        return norm_token(value)


def _bool_token(value: Any) -> str:
    if value is True:
        return "1"
    if value is False:
        return "0"
    return ""


def _dimensions(card: dict[str, Any]) -> dict[str, str]:
    identity = _identity(card)
    return {
        "card_number": _norm_card_number(identity.get("card_number")),
        "parallel": norm_token(identity.get("parallel")),
        "serial_total": norm_token(identity.get("serial_total")),
        "grader": norm_token(identity.get("grader")),
        "grade": _norm_grade(identity.get("grade")),
        "autograph": _bool_token(identity.get("autograph")),
        "memorabilia": _bool_token(identity.get("memorabilia")),
        "rookie": _bool_token(identity.get("rookie")),
    }


def _pair_bucket(left: dict[str, Any], right: dict[str, Any]) -> tuple[str, list[str]]:
    if _product_key(left) != _product_key(right):
        return "DIFFERENT_PRODUCT", ["product"]

    left_dims = _dimensions(left)
    right_dims = _dimensions(right)
    differences: list[str] = []
    missing: list[str] = []

    for field in left_dims:
        a = left_dims[field]
        b = right_dims[field]
        if a and b and a != b:
            differences.append(field)
        elif bool(a) != bool(b):
            missing.append(field)

    if differences:
        return "SAME_PRODUCT_DIFFERENT_VARIANT", differences
    if missing:
        return "SAME_PRODUCT_INCOMPLETE_IDENTITY", missing
    return "SAME_PRODUCT_SAME_KNOWN_IDENTITY", []


def _safe_example(left: dict[str, Any], right: dict[str, Any], bucket: str, reasons: list[str]) -> dict[str, Any]:
    identity = _identity(left)
    return {
        "bucket": bucket,
        "reasons": reasons,
        "sport": left.get("sport"),
        "player": identity.get("player"),
        "year": identity.get("year"),
        "left": {
            "source": left.get("source"),
            "external_id": left.get("external_id"),
            "title": left.get("title"),
            "url": left.get("url"),
        },
        "right": {
            "source": right.get("source"),
            "external_id": right.get("external_id"),
            "title": right.get("title"),
            "url": right.get("url"),
        },
    }


def build_overlap_report(cards: list[dict[str, Any]], *, example_limit: int = 25) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        key = _player_year_key(card)
        if key:
            grouped[key].append(card)

    bucket_counts: Counter[str] = Counter()
    mismatch_counts: Counter[str] = Counter()
    pair_counts: dict[str, Counter[str]] = defaultdict(Counter)
    examples: list[dict[str, Any]] = []
    cross_store_pairs = 0

    for rows in grouped.values():
        for left, right in combinations(rows, 2):
            left_source = str(left.get("source") or "UNKNOWN")
            right_source = str(right.get("source") or "UNKNOWN")
            if left_source == right_source:
                continue

            cross_store_pairs += 1
            store_pair = " <> ".join(sorted((left_source, right_source)))
            bucket, reasons = _pair_bucket(left, right)
            bucket_counts[bucket] += 1
            pair_counts[store_pair][bucket] += 1
            for reason in reasons:
                mismatch_counts[reason] += 1
                pair_counts[store_pair][f"reason:{reason}"] += 1

            if len(examples) < example_limit and bucket != "DIFFERENT_PRODUCT":
                examples.append(_safe_example(left, right, bucket, reasons))

    return {
        "cards": len(cards),
        "cross_store_player_year_pairs": cross_store_pairs,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "mismatch_dimension_counts": dict(sorted(mismatch_counts.items(), key=lambda item: (-item[1], item[0]))),
        "store_pairs": {
            pair: dict(sorted(counts.items()))
            for pair, counts in sorted(pair_counts.items())
        },
        "near_match_examples": examples,
        "governance": {
            "diagnostics_are_price_comparisons": False,
            "near_matches_are_exact_equivalents": False,
            "can_create_buy": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit deterministic cross-store inventory overlap without weakening exact matching.")
    parser.add_argument("--feed", default="docs/active_market.json")
    parser.add_argument("--output", default="artifacts/cross_store_overlap_audit.json")
    parser.add_argument("--example-limit", type=int, default=25)
    args = parser.parse_args()

    payload = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    report = build_overlap_report(
        list(payload.get("market_cards") or []),
        example_limit=max(0, args.example_limit),
    )
    report["feed_generated_at"] = payload.get("generated_at")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("CARD_SCANNER_CROSS_STORE_OVERLAP_AUDIT=PASS")
    print(f"MARKET_CARDS={report['cards']}")
    print(f"CROSS_STORE_PLAYER_YEAR_PAIRS={report['cross_store_player_year_pairs']}")
    for bucket, count in report["bucket_counts"].items():
        print(f"OVERLAP_{bucket}={count}")
    for field, count in report["mismatch_dimension_counts"].items():
        print(f"MISMATCH_{field.upper()}={count}")
    for pair, counts in report["store_pairs"].items():
        label = pair.upper().replace(" ", "_").replace("<>", "VS").replace("-", "_")
        print(f"STORE_PAIR_{label}_PAIRS={sum(v for k, v in counts.items() if not k.startswith('reason:'))}")
    print("NEAR_MATCHES_ARE_EXACT_EQUIVALENTS=NO")
    print("OVERLAP_DIAGNOSTICS_CAN_CREATE_BUY=NO")
    print(f"AUDIT_JSON={output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
