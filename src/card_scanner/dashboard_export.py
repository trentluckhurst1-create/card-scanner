from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from .identity_diagnostics import build_identity_diagnostics
from .market_catalogue import MarketListingObservation
from .models import Listing
from .opportunity_scanner import OpportunityScanResult, OpportunityScanSummary


DASHBOARD_SCHEMA_VERSION = 1
GOVERNANCE = (
    "Active asks are comparison evidence only, not fair value",
    "BUY and STRONG_BUY require genuine sold evidence",
    "Minimum sold-comp gate remains unchanged",
    "Research priority cannot manufacture fair value",
    "Raw sold API responses are not persisted or exported",
)
FAMILY_MATCH_RULE = "STRICT_STRUCTURED_IDENTITY"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round_money(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _round_score(value: Any, digits: int = 3) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _identity_from_listing(listing: Listing) -> dict[str, Any]:
    identity = listing.identity
    if identity is None:
        return {}
    return {
        "player": identity.player,
        "year": identity.year,
        "brand": identity.brand,
        "set_name": identity.set_name,
        "card_number": identity.card_number,
        "parallel": identity.parallel,
        "serial_current": getattr(identity, "serial_current", None),
        "serial_total": identity.serial_total,
        "grader": identity.grader,
        "grade": identity.grade,
        "autograph": identity.autograph,
        "memorabilia": identity.memorabilia,
        "rookie": getattr(identity, "rookie", None),
    }


def _identity_payload(result: OpportunityScanResult) -> dict[str, Any]:
    return _identity_from_listing(result.listing)


def _normalise_family_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value).casefold().strip()
    return re.sub(r"[^a-z0-9]+", "", text)


def canonical_family_key(*, sport: str, identity: dict[str, Any]) -> str | None:
    player = _normalise_family_value(identity.get("player"))
    year = _normalise_family_value(identity.get("year"))
    brand = _normalise_family_value(identity.get("brand") or identity.get("set_name"))
    discriminator_present = any(
        _normalise_family_value(identity.get(field))
        for field in ("card_number", "parallel", "serial_total")
    )
    if not player or not year or not brand or not discriminator_present:
        return None

    fields = (
        sport,
        identity.get("player"),
        identity.get("year"),
        identity.get("brand"),
        identity.get("set_name"),
        identity.get("card_number"),
        identity.get("parallel"),
        identity.get("serial_total"),
        identity.get("grader"),
        identity.get("grade"),
        identity.get("autograph"),
        identity.get("memorabilia"),
        identity.get("rookie"),
    )
    signature = "|".join(_normalise_family_value(value) for value in fields)
    return "cf_" + hashlib.sha256(signature.encode("utf-8")).hexdigest()[:20]


def _history_payload_from_assessment(history) -> dict[str, Any] | None:
    if history is None:
        return None
    return {
        "status": history.history_status,
        "first_seen_at": history.first_seen_at.isoformat(),
        "last_seen_at": history.last_seen_at.isoformat(),
        "age_days": history.age_days,
        "observation_count": history.observation_count,
        "previous_price": _round_money(history.previous_price),
        "current_price": _round_money(history.current_price),
        "min_observed_price": _round_money(history.min_observed_price),
        "max_observed_price": _round_money(history.max_observed_price),
        "price_change_count": history.price_change_count,
        "price_drop_count": history.price_drop_count,
        "price_increase_count": history.price_increase_count,
        "price_change_amount": _round_money(history.price_change_amount),
        "price_change_pct": _round_score(history.price_change_pct, 2),
        "latest_price_drop_pct": _round_score(history.latest_price_drop_pct, 2),
        "is_new": history.is_new,
        "is_price_drop": history.is_price_drop,
        "is_price_increase": history.is_price_increase,
        "is_stale": history.is_stale,
        "is_relisted": history.is_relisted,
    }


def _history_payload(result: OpportunityScanResult) -> dict[str, Any] | None:
    return _history_payload_from_assessment(result.listing_history)


def _landed_aud(listing: Listing) -> float | None:
    if listing.currency.upper() != "AUD":
        return None
    return _round_money(float(listing.price) + float(listing.shipping or 0.0))


def _family_payload(listing: Listing, identity: dict[str, Any]) -> dict[str, Any]:
    key = canonical_family_key(sport=listing.sport.upper(), identity=identity)
    return {"key": key, "eligible": key is not None, "match_rule": FAMILY_MATCH_RULE}


def market_listing_to_dashboard_record(observation: MarketListingObservation) -> dict[str, Any]:
    listing = observation.listing
    identity = _identity_from_listing(listing)
    return {
        "source": listing.source,
        "external_id": listing.external_id,
        "url": listing.url,
        "image_url": listing.image_url,
        "title": listing.title,
        "sport": listing.sport.upper(),
        "asking_price": _round_money(listing.price),
        "shipping": _round_money(listing.shipping),
        "currency": listing.currency.upper(),
        "landed_aud": _landed_aud(listing),
        "identity": identity,
        "card_family": _family_payload(listing, identity),
        "history": _history_payload_from_assessment(observation.history),
        "research_status": "NOT_RESEARCHED_IN_THIS_SCAN",
    }


def _cross_store_payload(result: OpportunityScanResult) -> dict[str, Any] | None:
    reference = result.cross_store_reference
    if reference is None:
        return None
    return {
        "status": getattr(reference, "status", None),
        "accepted_count": getattr(reference, "accepted_count", None),
        "exact_count": getattr(reference, "exact_count", None),
        "strong_count": getattr(reference, "strong_count", None),
        "stores_considered": getattr(reference, "stores_considered", None),
        "stores_searched": getattr(reference, "stores_searched", None),
        "lowest_aud": _round_money(getattr(reference, "lowest_aud", None)),
        "median_aud": _round_money(getattr(reference, "median_aud", None)),
        "trimmed_median_aud": _round_money(getattr(reference, "trimmed_median_aud", None)),
        "discount_to_lowest_pct": _round_score(getattr(reference, "discount_to_lowest_pct", None), 2),
        "discount_to_median_pct": _round_score(getattr(reference, "discount_to_median_pct", None), 2),
        "confidence": _round_score(getattr(reference, "confidence", None)),
    }


def _research_payload(result: OpportunityScanResult) -> dict[str, Any] | None:
    research = result.research_priority
    if research is None:
        return None
    return {
        "score": _round_score(research.score, 1),
        "priority": research.priority,
        "reasons": list(research.reasons),
        "cautions": list(research.cautions),
        "can_create_buy": False,
        "fair_value_aud": None,
    }


def result_to_dashboard_record(result: OpportunityScanResult) -> dict[str, Any]:
    listing = result.listing
    valuation = result.valuation
    opportunity = result.opportunity
    identity = _identity_payload(result)
    fair_value = _round_money(getattr(valuation, "fair_value_aud", None)) if getattr(valuation, "status", None) == "VALUED" else None
    return {
        "source": listing.source,
        "external_id": listing.external_id,
        "url": listing.url,
        "image_url": listing.image_url,
        "title": listing.title,
        "sport": listing.sport.upper(),
        "asking_price": _round_money(listing.price),
        "shipping": _round_money(listing.shipping),
        "currency": listing.currency.upper(),
        "landed_aud": _landed_aud(listing),
        "identity_quality": _round_score(result.identity_quality),
        "identity": identity,
        "card_family": _family_payload(listing, identity),
        "history": _history_payload(result),
        "active_market_reference": _cross_store_payload(result),
        "sold_evidence": {
            "status": getattr(valuation, "status", None),
            "accepted_count": result.accepted_count,
            "exact_count": result.exact_count,
            "strong_count": result.strong_count,
            "fetched_count": result.fetched_count,
        },
        "valuation": {
            "status": getattr(valuation, "status", None),
            "fair_value_aud": fair_value,
            "edge_pct": _round_score(getattr(opportunity, "edge_pct", None), 2) if fair_value is not None else None,
        },
        "research": _research_payload(result),
        "opportunity_status": opportunity.status,
        "research_status": "RESEARCHED",
    }


def _build_cross_store_families(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        key = (card.get("card_family") or {}).get("key")
        if key:
            grouped.setdefault(key, []).append(card)

    families: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        stores = sorted({str(row.get("source")) for row in rows if row.get("source")})
        if len(stores) < 2:
            continue
        priced = [float(row["landed_aud"]) for row in rows if row.get("landed_aud") is not None]
        lowest = min(priced) if priced else None
        highest = max(priced) if priced else None
        spread_pct = ((highest - lowest) / lowest) * 100.0 if lowest is not None and highest is not None and lowest > 0 else None
        representative = rows[0]
        families.append(
            {
                "key": key,
                "match_rule": FAMILY_MATCH_RULE,
                "pricing_basis": "ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE",
                "sport": representative.get("sport"),
                "identity": representative.get("identity") or {},
                "listing_count": len(rows),
                "store_count": len(stores),
                "stores": stores,
                "lowest_active_ask_aud": _round_money(lowest),
                "median_active_ask_aud": _round_money(median(priced)) if priced else None,
                "highest_active_ask_aud": _round_money(highest),
                "active_ask_spread_pct": _round_score(spread_pct, 2),
                "listings": [
                    {"source": row.get("source"), "external_id": row.get("external_id"), "url": row.get("url"), "landed_aud": row.get("landed_aud")}
                    for row in sorted(rows, key=lambda item: (item.get("landed_aud") is None, item.get("landed_aud") or 0, str(item.get("source") or "")))
                ],
            }
        )

    return sorted(families, key=lambda family: (-int(family["store_count"]), -float(family.get("active_ask_spread_pct") or 0), str(family["key"])))


def _fallback_market_observations(summary: OpportunityScanSummary) -> list[MarketListingObservation]:
    return [MarketListingObservation(listing=row.listing, history=row.listing_history) for row in summary.results]


def build_dashboard_payload(summary: OpportunityScanSummary, *, generated_at: str | None = None, market_listings: Iterable[MarketListingObservation] | None = None) -> dict[str, Any]:
    research_cards = [result_to_dashboard_record(row) for row in summary.results]
    observations = list(market_listings) if market_listings is not None else _fallback_market_observations(summary)
    market_cards = [market_listing_to_dashboard_record(row) for row in observations]
    families = _build_cross_store_families(market_cards)
    identity_diagnostics = build_identity_diagnostics(observations)
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": generated_at or _iso_now(),
        "stage": "Stage 7 — Persistent Market Monitoring",
        "metrics": {
            "fetched_listings": summary.fetched_listings,
            "market_cards": len(market_cards),
            "candidates_scanned": summary.candidates_scanned,
            "valued": summary.valued_count,
            "strong_buy": summary.strong_buy_count,
            "buy": summary.buy_count,
            "watch": summary.watch_count,
            "insufficient_sold_comps": summary.insufficient_comps_count,
            "insufficient_identity": summary.insufficient_identity_count,
            "sold_queries_used": summary.sold_queries_used,
            "history_observed": summary.history_observed_count,
            "history_new": summary.history_new_count,
            "history_price_drops": summary.history_price_drop_count,
            "history_price_increases": summary.history_price_increase_count,
            "history_relisted": summary.history_relisted_count,
            "history_stale": summary.history_stale_count,
            "cross_store_families": len(families),
            "family_eligible": identity_diagnostics["family_eligible_count"],
            "family_ineligible": identity_diagnostics["family_ineligible_count"],
            "sold_research_identity_ready": identity_diagnostics["sold_research_ready_count"],
            "sold_research_identity_not_ready": identity_diagnostics["sold_research_not_ready_count"],
            "sold_research_identity_ready_pct": identity_diagnostics["sold_research_ready_pct"],
            "sold_research_identity_threshold": identity_diagnostics["sold_identity_quality_threshold"],
        },
        "governance": list(GOVERNANCE),
        "identity_diagnostics": identity_diagnostics,
        "market_cards": market_cards,
        "cards": research_cards,
        "cross_store_families": families,
    }


def write_dashboard_payload(summary: OpportunityScanSummary, path: str | Path, *, generated_at: str | None = None, market_listings: Iterable[MarketListingObservation] | None = None) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_dashboard_payload(summary, generated_at=generated_at, market_listings=market_listings)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
