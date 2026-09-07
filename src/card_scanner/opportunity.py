from __future__ import annotations

from .comp_key import comp_quality
from .config import settings
from .landed_cost import cherry_landed_cost
from .models import Listing, Opportunity, RiskFlag, SoldValuation
from .risk import risk_score


def assess_opportunity(
    listing: Listing,
    valuation: SoldValuation,
    risk_flags: list[RiskFlag] | None = None,
) -> Opportunity:
    risk_flags = risk_flags or []
    identity_confidence = comp_quality(listing.identity) if listing.identity else 0.0
    landed = cherry_landed_cost(listing)
    risk = risk_score(risk_flags)
    reasons: list[str] = []

    if identity_confidence < settings.opportunity_min_identity_confidence:
        reasons.append("identity confidence below threshold")
        return Opportunity(
            source_listing_external_id=listing.external_id,
            landed_cost_aud=landed.landed_cost_aud,
            identity_confidence=identity_confidence,
            comp_confidence=valuation.comp_confidence,
            liquidity_score=valuation.liquidity_score,
            risk_score=risk,
            market_direction=valuation.market_direction,
            status="INSUFFICIENT_IDENTITY",
            reasons=reasons,
        )

    if valuation.fair_value_aud is None or valuation.status != "VALUED":
        reasons.append("genuine sold comp evidence is insufficient")
        return Opportunity(
            source_listing_external_id=listing.external_id,
            landed_cost_aud=landed.landed_cost_aud,
            identity_confidence=identity_confidence,
            comp_confidence=valuation.comp_confidence,
            liquidity_score=valuation.liquidity_score,
            risk_score=risk,
            market_direction=valuation.market_direction,
            status="INSUFFICIENT_SOLD_COMPS",
            reasons=reasons,
        )

    if landed.landed_cost_aud is None or landed.landed_cost_aud <= 0:
        reasons.append("landed cost is unknown")
        return Opportunity(
            source_listing_external_id=listing.external_id,
            fair_value_aud=valuation.fair_value_aud,
            quick_sale_value_aud=valuation.quick_sale_value_aud,
            identity_confidence=identity_confidence,
            comp_confidence=valuation.comp_confidence,
            liquidity_score=valuation.liquidity_score,
            risk_score=risk,
            market_direction=valuation.market_direction,
            status="INSUFFICIENT_SOLD_COMPS",
            reasons=reasons,
        )

    edge_pct = (valuation.fair_value_aud - landed.landed_cost_aud) / landed.landed_cost_aud * 100.0

    if risk >= 60.0:
        status = "HIGH_RISK"
        reasons.append("risk severity is too high")
    elif edge_pct < -10.0:
        status = "OVERPRICED"
        reasons.append("sold comp fair value is below landed cost")
    elif edge_pct < 10.0:
        status = "FAIR"
        reasons.append("edge is not large enough for watch or buy")
    elif (
        valuation.comp_confidence < settings.opportunity_min_comp_confidence
        or valuation.sold_comp_count < settings.min_total_comps_medium_confidence
    ):
        status = "WATCH"
        reasons.append("positive edge but comp confidence/depth is limited")
    elif edge_pct >= settings.opportunity_strong_buy_edge_pct:
        status = "STRONG_BUY"
        reasons.append("sold comp edge clears strong buy threshold")
    elif edge_pct >= settings.opportunity_buy_edge_pct:
        status = "BUY"
        reasons.append("sold comp edge clears buy threshold")
    else:
        status = "WATCH"
        reasons.append("positive edge below buy threshold")

    confidence_component = valuation.comp_confidence * 35.0
    liquidity_component = valuation.liquidity_score * 20.0
    identity_component = identity_confidence * 20.0
    edge_component = max(0.0, min(edge_pct, 60.0)) / 60.0 * 25.0
    penalty = risk * 0.35
    score = max(
        0.0,
        min(
            100.0,
            confidence_component + liquidity_component + identity_component + edge_component - penalty,
        ),
    )

    return Opportunity(
        source_listing_external_id=listing.external_id,
        landed_cost_aud=round(landed.landed_cost_aud, 2),
        fair_value_aud=valuation.fair_value_aud,
        quick_sale_value_aud=valuation.quick_sale_value_aud,
        edge_pct=round(edge_pct, 2),
        opportunity_score=round(score, 2),
        identity_confidence=identity_confidence,
        comp_confidence=valuation.comp_confidence,
        liquidity_score=valuation.liquidity_score,
        risk_score=risk,
        market_direction=valuation.market_direction,
        status=status,
        reasons=reasons,
    )
