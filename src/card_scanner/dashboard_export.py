from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .opportunity_scanner import OpportunityScanResult, OpportunityScanSummary


DASHBOARD_SCHEMA_VERSION = 1
GOVERNANCE = (
    "Active asks are comparison evidence only, not fair value",
    "BUY and STRONG_BUY require genuine sold evidence",
    "Minimum sold-comp gate remains unchanged",
    "Research priority cannot manufacture fair value",
    "Raw sold API responses are not persisted or exported",
)


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


def _identity_payload(result: OpportunityScanResult) -> dict[str, Any]:
    identity = result.listing.identity
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


def _history_payload(result: OpportunityScanResult) -> dict[str, Any] | None:
    history = result.listing_history
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
        "trimmed_median_aud": _round_money(
            getattr(reference, "trimmed_median_aud", None)
        ),
        "discount_to_lowest_pct": _round_score(
            getattr(reference, "discount_to_lowest_pct", None), 2
        ),
        "discount_to_median_pct": _round_score(
            getattr(reference, "discount_to_median_pct", None), 2
        ),
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

    fair_value = (
        _round_money(getattr(valuation, "fair_value_aud", None))
        if getattr(valuation, "status", None) == "VALUED"
        else None
    )
    landed_aud = (
        _round_money(float(listing.price) + float(listing.shipping or 0.0))
        if listing.currency.upper() == "AUD"
        else None
    )

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
        "landed_aud": landed_aud,
        "identity_quality": _round_score(result.identity_quality),
        "identity": _identity_payload(result),
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
            "edge_pct": (
                _round_score(getattr(opportunity, "edge_pct", None), 2)
                if fair_value is not None
                else None
            ),
        },
        "research": _research_payload(result),
        "opportunity_status": opportunity.status,
    }


def build_dashboard_payload(
    summary: OpportunityScanSummary,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "generated_at": generated_at or _iso_now(),
        "stage": "Stage 7 — Persistent Market Monitoring",
        "metrics": {
            "fetched_listings": summary.fetched_listings,
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
        },
        "governance": list(GOVERNANCE),
        "cards": [result_to_dashboard_record(row) for row in summary.results],
    }


def write_dashboard_payload(
    summary: OpportunityScanSummary,
    path: str | Path,
    *,
    generated_at: str | None = None,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_dashboard_payload(summary, generated_at=generated_at)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output
