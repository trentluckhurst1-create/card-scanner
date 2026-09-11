from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from card_scanner.active_price_comparison import build_active_price_comparisons
from card_scanner.dashboard_export import market_listing_to_dashboard_record
from card_scanner.fx import RbaFxProvider
from card_scanner.identity_match import (
    canonical_exact_components,
    exact_components_eligible,
    exact_signature,
)
from card_scanner.market_catalogue import MarketListingObservation
from card_scanner.sources.ebay import EbaySource


def _text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _source(value: object) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _signature_for_card(card: dict) -> tuple[str, dict[str, str]] | None:
    identity = card.get("identity") or {}
    sport = str(card.get("sport") or "").upper().strip()
    components = canonical_exact_components(sport=sport, identity=identity)
    if not exact_components_eligible(components):
        return None
    return exact_signature(components), components


def _target_query(card: dict) -> str:
    """Build a specific natural-language eBay query from the known card identity."""
    identity = card.get("identity") or {}
    parts: list[str] = []
    for value in (
        identity.get("year"),
        identity.get("player"),
        identity.get("set_name") or identity.get("brand"),
    ):
        text = " ".join(str(value or "").split())
        if text and text.casefold() not in {p.casefold() for p in parts}:
            parts.append(text)

    card_number = str(identity.get("card_number") or "").strip()
    if card_number:
        parts.append(card_number.lstrip("#"))

    parallel = " ".join(str(identity.get("parallel") or "").split())
    if parallel:
        parts.append(parallel)

    serial_total = identity.get("serial_total")
    if serial_total not in (None, ""):
        parts.append(f"/{serial_total}")

    grader = " ".join(str(identity.get("grader") or "").split())
    grade = identity.get("grade")
    if grader:
        parts.append(grader)
    if grade not in (None, ""):
        try:
            grade_number = float(grade)
            parts.append(str(int(grade_number)) if grade_number.is_integer() else str(grade_number))
        except (TypeError, ValueError):
            parts.append(str(grade))

    if bool(identity.get("autograph")):
        parts.append("auto")
    if bool(identity.get("memorabilia")):
        parts.append("relic")

    return " ".join(parts)


def _candidate_targets(cards: list[dict], max_targets: int) -> list[dict]:
    """Choose exact card signatures that do not already have an eBay listing.

    Discovery capacity is spent at card-signature level, not broad player/year
    level. That prevents thousands of unrelated same-player listings from being
    imported and focuses every Browse request on a card that can create a new
    cross-store comparison if eBay has the exact counterpart.
    """
    rows_by_signature: dict[str, list[dict]] = defaultdict(list)
    sources_by_signature: dict[str, set[str]] = defaultdict(set)
    components_by_signature: dict[str, dict[str, str]] = {}

    for card in cards:
        resolved = _signature_for_card(card)
        if resolved is None:
            continue
        signature, components = resolved
        rows_by_signature[signature].append(card)
        sources_by_signature[signature].add(_source(card.get("source")))
        components_by_signature[signature] = components

    candidates: list[dict] = []
    for signature, rows in rows_by_signature.items():
        sources = sources_by_signature[signature]
        if "ebay" in sources:
            continue
        representative = max(
            rows,
            key=lambda card: (
                bool((card.get("identity") or {}).get("card_number")),
                bool((card.get("identity") or {}).get("parallel")),
                bool((card.get("identity") or {}).get("serial_total")),
                len(str(card.get("title") or "")),
            ),
        )
        query = _target_query(representative)
        if not query:
            continue
        candidates.append(
            {
                "signature": signature,
                "components": components_by_signature[signature],
                "sport": str(representative.get("sport") or "").upper(),
                "player": str((representative.get("identity") or {}).get("player") or "").strip(),
                "query": query,
                "source_count": len(sources),
                "listing_count": len(rows),
            }
        )

    candidates.sort(
        key=lambda target: (
            0 if target["source_count"] == 1 else 1,
            -target["listing_count"],
            target["sport"],
            target["player"].casefold(),
            target["signature"],
        )
    )
    return candidates[: max(0, int(max_targets))]


def _record_with_aud(row, fx_provider: RbaFxProvider, rate_date) -> dict:
    record = market_listing_to_dashboard_record(
        MarketListingObservation(listing=row)
    )
    currency = str(row.currency or "").upper()
    total = float(row.price) + float(row.shipping or 0.0)
    if currency == "AUD":
        record["fx_status"] = "AUD_NATIVE"
        record["fx_source"] = "AUD_NATIVE"
        record["fx_rate_date"] = rate_date.isoformat()
        return record

    conversion = fx_provider.convert_to_aud(total, currency, rate_date)
    record["landed_aud"] = conversion.aud_amount
    record["fx_status"] = conversion.status
    record["fx_source"] = conversion.source
    record["fx_rate_date"] = conversion.rate_date
    record["fx_foreign_per_aud"] = conversion.foreign_per_aud
    return record


def enrich_payload(
    payload: dict,
    *,
    max_targets: int = 24,
    results_per_target: int = 50,
    fx_provider: RbaFxProvider | None = None,
) -> dict:
    cards = list(payload.get("market_cards") or [])
    ebay = EbaySource()
    missing = ebay.missing_credentials()
    metrics = dict(payload.get("metrics") or {})
    metrics.update(
        {
            "ebay_enabled": not bool(missing),
            "ebay_targets": 0,
            "ebay_queries": 0,
            "ebay_added_cards": 0,
            "ebay_exact_signatures_matched": 0,
            "ebay_rejected_non_exact": 0,
            "ebay_errors": 0,
        }
    )
    if missing:
        payload["metrics"] = metrics
        payload["ebay_status"] = "DISABLED_MISSING_CREDENTIALS"
        return payload

    fx_provider = fx_provider or RbaFxProvider()
    rate_date = datetime.now(timezone.utc).date()
    targets = _candidate_targets(cards, max_targets=max_targets)
    metrics["ebay_targets"] = len(targets)
    seen = {
        (_source(card.get("source")), str(card.get("external_id") or ""))
        for card in cards
    }
    errors: list[str] = []
    matched_signatures: set[str] = set()

    for target in targets:
        metrics["ebay_queries"] += 1
        try:
            found = ebay.search(
                sport=target["sport"],
                query=target["query"],
                limit=max(1, int(results_per_target)),
            )
        except Exception as exc:
            errors.append(
                f"{target['sport']}: {target['player']}: {type(exc).__name__}: {exc}"
            )
            continue

        for row in found:
            identity = row.identity
            if identity is None:
                metrics["ebay_rejected_non_exact"] += 1
                continue
            components = canonical_exact_components(
                sport=row.sport,
                identity=identity.model_dump(),
            )
            if not exact_components_eligible(components):
                metrics["ebay_rejected_non_exact"] += 1
                continue
            if exact_signature(components) != target["signature"]:
                metrics["ebay_rejected_non_exact"] += 1
                continue

            key = (_source(row.source), str(row.external_id))
            if key in seen:
                continue
            seen.add(key)
            cards.append(_record_with_aud(row, fx_provider, rate_date))
            metrics["ebay_added_cards"] += 1
            matched_signatures.add(target["signature"])

    metrics["ebay_exact_signatures_matched"] = len(matched_signatures)
    metrics["ebay_errors"] = len(errors)
    metrics["active_cards"] = len(cards)
    metrics["foreign_currency_cards"] = sum(
        1 for card in cards if str(card.get("currency") or "").upper() != "AUD"
    )
    metrics["fx_converted_cards"] = sum(
        1 for card in cards if card.get("fx_status") == "CONVERTED"
    )
    payload["market_cards"] = cards
    payload["metrics"] = metrics
    payload["display_currency"] = "AUD"
    payload.setdefault("governance", {})["foreign_prices_converted_to_aud"] = True
    payload["governance"]["ebay_discovery_requires_exact_signature"] = True
    payload["ebay_status"] = "ENABLED"
    payload["ebay_errors"] = errors

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
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Targeted eBay Browse API enrichment for active market feed."
    )
    parser.add_argument("--feed", default="docs/active_market.json")
    parser.add_argument("--max-targets", type=int, default=24)
    parser.add_argument("--results-per-target", type=int, default=50)
    args = parser.parse_args()
    feed = Path(args.feed)
    payload = json.loads(feed.read_text(encoding="utf-8"))
    payload = enrich_payload(
        payload,
        max_targets=max(0, args.max_targets),
        results_per_target=max(1, args.results_per_target),
    )
    feed.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metrics = payload.get("metrics") or {}
    print(f"EBAY_STATUS={payload.get('ebay_status')}")
    print(f"EBAY_TARGETS={metrics.get('ebay_targets', 0)}")
    print(f"EBAY_QUERIES={metrics.get('ebay_queries', 0)}")
    print(f"EBAY_ADDED_CARDS={metrics.get('ebay_added_cards', 0)}")
    print(f"EBAY_EXACT_SIGNATURES_MATCHED={metrics.get('ebay_exact_signatures_matched', 0)}")
    print(f"EBAY_REJECTED_NON_EXACT={metrics.get('ebay_rejected_non_exact', 0)}")
    print(f"EBAY_ERRORS={metrics.get('ebay_errors', 0)}")
    print(f"FOREIGN_CURRENCY_CARDS={metrics.get('foreign_currency_cards', 0)}")
    print(f"FX_CONVERTED_CARDS={metrics.get('fx_converted_cards', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
