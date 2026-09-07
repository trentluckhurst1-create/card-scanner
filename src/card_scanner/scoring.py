from __future__ import annotations
from .models import Listing, Valuation

def score_listing(
    listing: Listing,
    fair_value_aud: float | None,
    quick_sale_value_aud: float | None,
    comp_count: int,
    comp_confidence: float,
    liquidity: float,
    identity_confidence: float,
    risk_penalty: float = 0.0,
    landed_cost_aud: float | None = None,
) -> Valuation:
    landed = landed_cost_aud if landed_cost_aud is not None else listing.price + listing.shipping

    if fair_value_aud is None or fair_value_aud <= 0 or landed <= 0:
        return Valuation(
            listing_external_id=listing.external_id,
            landed_cost_aud=landed,
            fair_value_aud=fair_value_aud,
            quick_sale_value_aud=quick_sale_value_aud,
            comp_count=comp_count,
            comp_confidence=comp_confidence,
            liquidity=liquidity,
            identity_confidence=identity_confidence,
            risk_penalty=risk_penalty,
            opportunity_score=0.0,
            edge_pct=None,
        )

    edge = (fair_value_aud - landed) / landed * 100.0

    # Edge is capped so one noisy comp cannot dominate.
    edge_component = max(0.0, min(edge, 100.0))
    confidence_component = 100.0 * max(0.0, min(comp_confidence, 1.0))
    liquidity_component = 100.0 * max(0.0, min(liquidity, 1.0))
    identity_component = 100.0 * max(0.0, min(identity_confidence, 1.0))
    comp_depth_component = min(comp_count / 8.0, 1.0) * 100.0

    score = (
        0.35 * edge_component
        + 0.22 * confidence_component
        + 0.15 * liquidity_component
        + 0.18 * identity_component
        + 0.10 * comp_depth_component
        - max(0.0, min(risk_penalty, 100.0))
    )
    score = max(0.0, min(score, 100.0))

    return Valuation(
        listing_external_id=listing.external_id,
        landed_cost_aud=round(landed, 2),
        fair_value_aud=round(fair_value_aud, 2),
        quick_sale_value_aud=round(quick_sale_value_aud, 2) if quick_sale_value_aud else None,
        comp_count=comp_count,
        comp_confidence=comp_confidence,
        liquidity=liquidity,
        identity_confidence=identity_confidence,
        risk_penalty=risk_penalty,
        opportunity_score=round(score, 2),
        edge_pct=round(edge, 2),
    )
