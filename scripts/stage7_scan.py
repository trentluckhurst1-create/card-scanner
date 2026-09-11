from __future__ import annotations

import argparse
import json
from pathlib import Path

from card_scanner.active_price_comparison import build_active_price_comparisons
from card_scanner.cli import opportunity_store_source
from card_scanner.dashboard_export import write_dashboard_payload
from card_scanner.db import init_db
from card_scanner.market_catalogue import capture_store_source, catalogue_observations
from card_scanner.opportunity_scanner import scan_store_opportunities
from card_scanner.the_card_api import TheCardApiSoldCompProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the governed Stage 7 multi-store scan with persistent active-listing "
            "history and emit the safe public dashboard feed."
        )
    )
    parser.add_argument("--source", default="all")
    parser.add_argument("--sport", default="ALL")
    parser.add_argument("--listings-per-sport", type=int, default=30)
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--sold-limit", type=int, default=100)
    parser.add_argument("--max-sold-queries", type=int, default=20)
    parser.add_argument(
        "--dashboard-json",
        default="docs/market.json",
        help="Safe generated dashboard feed path.",
    )
    parser.add_argument(
        "--no-record-history",
        action="store_true",
        help="Diagnostic escape hatch. Normal Stage 7 scans record active-listing history.",
    )
    return parser


def _publish_active_price_comparisons(output: Path) -> dict:
    payload = json.loads(output.read_text(encoding="utf-8"))
    comparisons = build_active_price_comparisons(payload.get("market_cards") or [])
    payload["active_price_comparisons"] = comparisons
    metrics = payload.setdefault("metrics", {})
    metrics["price_comparison_groups"] = comparisons["comparison_group_count"]
    metrics["exact_price_comparison_groups"] = comparisons["exact_match_count"]
    metrics["same_product_variant_groups"] = comparisons["same_product_variant_count"]
    metrics["player_year_market_groups"] = comparisons["player_year_market_count"]
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    args = build_parser().parse_args()
    record_history = not args.no_record_history

    try:
        raw_store_source, source_label = opportunity_store_source(args.source)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    store_source = capture_store_source(raw_store_source)

    provider = TheCardApiSoldCompProvider()
    if provider.missing_credentials():
        raise SystemExit("Missing THE_CARD_API_KEY in local .env.")

    if record_history:
        init_db()

    summary = scan_store_opportunities(
        store_source=store_source,
        sold_provider=provider,
        sport=args.sport.upper(),
        listings_per_sport=args.listings_per_sport,
        max_candidates_per_sport=args.max_candidates,
        sold_results_per_query=args.sold_limit,
        max_sold_queries=args.max_sold_queries,
        record_history=record_history,
    )

    market_listings = catalogue_observations(
        store_source,
        include_history=record_history,
    )
    output = write_dashboard_payload(
        summary,
        Path(args.dashboard_json),
        market_listings=market_listings,
    )
    payload = _publish_active_price_comparisons(Path(output))
    diagnostics = payload.get("identity_diagnostics") or {}
    gap_counts = diagnostics.get("gap_counts") or {}
    sold_reason_counts = diagnostics.get("sold_not_ready_reason_counts") or {}
    comparisons = payload.get("active_price_comparisons") or {}

    print("CARD_SCANNER_STAGE7_SCAN=PASS")
    print(f"SOURCE={source_label}")
    print(f"SPORT={args.sport.upper()}")
    print(f"FETCHED_LISTINGS={summary.fetched_listings}")
    print(f"MARKET_CATALOGUE={len(market_listings)}")
    print(f"CANDIDATES_SCANNED={summary.candidates_scanned}")
    print(f"VALUED={summary.valued_count}")
    print(f"BUY={summary.buy_count}")
    print(f"STRONG_BUY={summary.strong_buy_count}")
    print(f"INSUFFICIENT_SOLD_COMPS={summary.insufficient_comps_count}")
    print(f"INSUFFICIENT_IDENTITY={summary.insufficient_identity_count}")
    print(f"PRICE_COMPARISON_GROUPS={comparisons.get('comparison_group_count', 0)}")
    print(f"EXACT_PRICE_COMPARISON_GROUPS={comparisons.get('exact_match_count', 0)}")
    print(f"SAME_PRODUCT_VARIANT_GROUPS={comparisons.get('same_product_variant_count', 0)}")
    print(f"PLAYER_YEAR_MARKET_GROUPS={comparisons.get('player_year_market_count', 0)}")
    print(f"FAMILY_ELIGIBLE={diagnostics.get('family_eligible_count', 0)}")
    print(f"FAMILY_INELIGIBLE={diagnostics.get('family_ineligible_count', 0)}")
    print(f"FAMILY_ELIGIBLE_PCT={diagnostics.get('family_eligible_pct', 0.0)}")
    print(f"SOLD_RESEARCH_IDENTITY_READY={diagnostics.get('sold_research_ready_count', 0)}")
    print(f"SOLD_RESEARCH_IDENTITY_NOT_READY={diagnostics.get('sold_research_not_ready_count', 0)}")
    print(f"SOLD_RESEARCH_IDENTITY_READY_PCT={diagnostics.get('sold_research_ready_pct', 0.0)}")
    print(f"SOLD_RESEARCH_IDENTITY_THRESHOLD={diagnostics.get('sold_identity_quality_threshold', 0.0)}")
    for reason, count in sorted(sold_reason_counts.items()):
        print(f"SOLD_RESEARCH_NOT_READY_{reason}={count}")
    for band, count in sorted((diagnostics.get("identity_quality_bands") or {}).items()):
        print(f"IDENTITY_QUALITY_BAND_{band}={count}")
    for gap in (
        "NO_IDENTITY",
        "MISSING_PLAYER",
        "MISSING_YEAR",
        "MISSING_BRAND_OR_SET",
        "MISSING_STRUCTURED_DISCRIMINATOR",
    ):
        print(f"IDENTITY_{gap}={gap_counts.get(gap, 0)}")
    for source_row in diagnostics.get("by_source") or []:
        source = str(source_row.get("source") or "UNKNOWN").upper().replace(" ", "_")
        print(f"IDENTITY_SOURCE_{source}_LISTINGS={source_row.get('listing_count', 0)}")
        print(f"IDENTITY_SOURCE_{source}_FAMILY_ELIGIBLE={source_row.get('family_eligible_count', 0)}")
        print(f"IDENTITY_SOURCE_{source}_FAMILY_ELIGIBLE_PCT={source_row.get('family_eligible_pct', 0.0)}")
        print(f"IDENTITY_SOURCE_{source}_SOLD_RESEARCH_READY={source_row.get('sold_research_ready_count', 0)}")
        print(f"IDENTITY_SOURCE_{source}_SOLD_RESEARCH_READY_PCT={source_row.get('sold_research_ready_pct', 0.0)}")
        print(f"IDENTITY_SOURCE_{source}_MEAN_QUALITY={source_row.get('mean_identity_quality', 0.0)}")
        for reason, count in sorted((source_row.get("sold_not_ready_reason_counts") or {}).items()):
            print(f"IDENTITY_SOURCE_{source}_SOLD_NOT_READY_{reason}={count}")
        for gap, count in sorted((source_row.get("gap_counts") or {}).items()):
            print(f"IDENTITY_SOURCE_{source}_{gap}={count}")
    print(f"HISTORY_OBSERVED={summary.history_observed_count}")
    print(f"HISTORY_NEW={summary.history_new_count}")
    print(f"HISTORY_UNCHANGED={summary.history_unchanged_count}")
    print(f"HISTORY_PRICE_DROPS={summary.history_price_drop_count}")
    print(f"HISTORY_PRICE_INCREASES={summary.history_price_increase_count}")
    print(f"HISTORY_RELISTED={summary.history_relisted_count}")
    print(f"HISTORY_STALE={summary.history_stale_count}")
    print(f"HISTORY_EVENTS={summary.history_event_count}")
    print(f"HISTORY_ERRORS={len(summary.history_errors)}")
    print(f"REFERENCE_STORE_ERRORS={len(summary.reference_store_errors)}")
    print(f"DASHBOARD_JSON={output}")
    print(f"PROVIDER_HTTP_QUERIES={provider.query_count}")
    print("ACTIVE_PRICE_COMPARISONS_ARE_FAIR_VALUE=NO")
    print("RELATED_VARIANTS_ARE_EXACT_EQUIVALENTS=NO")
    print("ACTIVE_STORE_REFETCH_FOR_CATALOGUE=NO")
    print("IDENTITY_DIAGNOSTICS_CAN_RELAX_GATES=NO")
    print("RAW_API_PERSISTENCE=NO")
    print("API_SOLD_ROWS_PERSISTED=0")
    print("API_SOLD_MATCHES_PERSISTED=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
