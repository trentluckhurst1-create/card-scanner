from __future__ import annotations

from dataclasses import dataclass

from .listing_history import ListingHistoryAssessment
from .market_reference import CrossStoreReference, MarketReferenceStatus
from .models import Listing, Opportunity, RiskFlag, SoldValuation
from .underdescription import UnderdescriptionAssessment


@dataclass(frozen=True)
class MispricingAssessment:
    score: float
    why_it_looks_cheap: tuple[str, ...]
    why_it_may_be_cheap: tuple[str, ...]
    evidence_flags: tuple[str, ...]
    suppressions: tuple[str, ...]


def _add_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _pct(value: object | None) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sold_evidence_score(
    valuation: SoldValuation,
) -> float:
    score = 0.0

    if valuation.exact_comp_count >= 3:
        score += 16.0
    elif valuation.exact_comp_count:
        score += 6.0

    score += min(valuation.sold_comp_count, 8) / 8.0 * 12.0
    score += max(0.0, min(valuation.comp_confidence, 1.0)) * 18.0
    score += max(0.0, min(valuation.liquidity_score, 1.0)) * 10.0

    median_age = _pct(valuation.explanation.get("median_comp_age_days"))
    if median_age is not None:
        if median_age <= 30:
            score += 5.0
        elif median_age <= 90:
            score += 3.0
        elif median_age <= 180:
            score += 1.0

    return score


def assess_mispricing(
    listing: Listing,
    valuation: SoldValuation,
    opportunity: Opportunity,
    risk_flags: list[RiskFlag] | None = None,
    cross_store_reference: CrossStoreReference | None = None,
    listing_history: ListingHistoryAssessment | None = None,
    underdescription: UnderdescriptionAssessment | None = None,
) -> MispricingAssessment:
    """
    Explain whether a cheap-looking card is a defensible mispricing.

    This is reporting/ranking logic only. It does not change valuation gates
    or create BUY-style decisions without genuine sold evidence.
    """
    risk_flags = risk_flags or []
    looks: list[str] = []
    may_be: list[str] = []
    evidence: list[str] = []
    suppressions: list[str] = []

    underdescription_penalty = 0.0

    if underdescription is not None:
        if underdescription.status == "POOR_IDENTITY":
            _add_once(
                may_be,
                "under-description risk: seller title has poor identity specificity",
            )
            _add_once(
                evidence,
                "UNDERDESCRIPTION_POOR_IDENTITY",
            )
            _add_once(
                suppressions,
                "poor title identity limits confidence in apparent mispricing",
            )
            underdescription_penalty = 8.0

        elif underdescription.status == "REVIEW":
            _add_once(
                may_be,
                "under-description risk: seller title needs identity review",
            )
            _add_once(
                evidence,
                "UNDERDESCRIPTION_REVIEW",
            )
            underdescription_penalty = 3.0

        for signal in underdescription.signals:
            _add_once(
                evidence,
                signal.code,
            )
    edge_pct = opportunity.edge_pct

    if edge_pct is not None and edge_pct >= 10.0:
        _add_once(
            looks,
            f"sold fair-value edge is {edge_pct:.1f}%",
        )

    if (
        valuation.quick_sale_value_aud is not None
        and opportunity.landed_cost_aud is not None
        and opportunity.landed_cost_aud <= valuation.quick_sale_value_aud
    ):
        _add_once(
            looks,
            "landed cost is below quick-sale value",
        )

    if valuation.exact_comp_count >= 3:
        _add_once(
            evidence,
            f"{valuation.exact_comp_count} exact sold comps",
        )
    elif valuation.strong_comp_count:
        _add_once(
            evidence,
            f"{valuation.strong_comp_count} strong sold comps",
        )

    median_age = _pct(valuation.explanation.get("median_comp_age_days"))
    if median_age is not None:
        _add_once(
            evidence,
            f"median comp age {median_age:.0f} days",
        )

    spread_pct = _pct(valuation.explanation.get("price_spread_pct"))
    mad_pct = _pct(
        valuation.explanation.get("median_absolute_deviation_pct")
    )

    if mad_pct is not None:
        _add_once(
            evidence,
            f"median absolute price deviation {mad_pct:.1f}%",
        )

    if cross_store_reference is not None:
        discount = cross_store_reference.candidate_discount_to_median_pct
        lowest_discount = (
            cross_store_reference.candidate_discount_to_lowest_pct
        )
        consensus_level = cross_store_reference.consensus_level
        consensus_strength = cross_store_reference.consensus_strength

        if (
            cross_store_reference.status
            == MarketReferenceStatus.REFERENCE_AVAILABLE
        ):
            if discount is not None and discount > 0:
                _add_once(
                    looks,
                    f"cross-store ask is {discount:.1f}% below median ask",
                )

            if lowest_discount is not None and lowest_discount > 0:
                _add_once(
                    evidence,
                    (
                        f"candidate is {lowest_discount:.1f}% below lowest "
                        "accepted competing ask"
                    ),
                )

            _add_once(
                evidence,
                (
                    f"{cross_store_reference.matched_listing_count} "
                    "cross-store active references"
                ),
            )

            _add_once(
                evidence,
                (
                    f"active-market consensus {consensus_level.lower()} "
                    f"({consensus_strength:.3f})"
                ),
            )

            if cross_store_reference.active_mad_pct is not None:
                _add_once(
                    evidence,
                    (
                        "active-market median absolute deviation "
                        f"{cross_store_reference.active_mad_pct:.1f}%"
                    ),
                )

            if cross_store_reference.active_price_spread_pct is not None:
                _add_once(
                    evidence,
                    (
                        "active-market price spread "
                        f"{cross_store_reference.active_price_spread_pct:.1f}%"
                    ),
                )

            if consensus_level == "WEAK":
                _add_once(
                    may_be,
                    "cross-market active-ask consensus is weak",
                )

        elif (
            cross_store_reference.status
            == MarketReferenceStatus.NO_REFERENCE
        ):
            _add_once(
                may_be,
                "no accepted cross-store active reference",
            )

        elif (
            cross_store_reference.status
            == MarketReferenceStatus.INSUFFICIENT_REFERENCE
        ):
            _add_once(
                may_be,
                "cross-store active reference depth is insufficient",
            )

    if listing_history is not None:
        if listing_history.is_new:
            _add_once(
                evidence,
                "first observed in current history window",
            )
            if edge_pct is not None and edge_pct >= 10.0:
                _add_once(
                    looks,
                    "new listing entered below defensible fair value",
                )

        if listing_history.is_price_drop:
            change_pct = listing_history.price_change_pct
            if change_pct is not None:
                _add_once(
                    looks,
                    f"price dropped {abs(change_pct):.1f}% since previous observation",
                )
            else:
                _add_once(
                    looks,
                    "price dropped since previous observation",
                )

        if listing_history.observation_count <= 1:
            _add_once(
                may_be,
                "history evidence is sparse",
            )

        if (
            listing_history.is_stale
            and edge_pct is not None
            and edge_pct >= 10.0
        ):
            _add_once(
                may_be,
                (
                    "listing has remained active for "
                    f"{listing_history.age_days} days despite apparent discount"
                ),
            )

        if listing_history.price_drop_count >= 2:
            _add_once(
                may_be,
                "repeated price reductions may indicate weaker market demand",
            )

    if opportunity.identity_confidence < 0.85:
        _add_once(
            may_be,
            "identity confidence is not high enough for escalation",
        )

    if valuation.status != "VALUED":
        _add_once(
            may_be,
            "genuine sold-comp evidence is insufficient",
        )
        _add_once(
            suppressions,
            "sold valuation unavailable",
        )

    if valuation.sold_comp_count < 3:
        _add_once(
            may_be,
            "fewer than three accepted sold comps",
        )

    if valuation.comp_confidence < 0.55:
        _add_once(
            may_be,
            "sold-comp confidence is limited",
        )

    if valuation.liquidity_score < 0.40:
        _add_once(
            may_be,
            "low recent sales liquidity",
        )

    if spread_pct is not None and spread_pct >= 60.0:
        _add_once(
            may_be,
            f"sold prices are widely dispersed ({spread_pct:.1f}%)",
        )

    if median_age is not None and median_age > 180:
        _add_once(
            may_be,
            "sold evidence is old",
        )

    if valuation.market_direction == "FALLING":
        _add_once(
            may_be,
            "recent sold market direction is falling",
        )

    if risk_flags:
        severe = [
            flag.code
            for flag in risk_flags
            if flag.severity.upper() in {"HIGH", "REJECT"}
        ]
        if severe:
            _add_once(
                may_be,
                "listing title contains rejecting/high risk language: "
                + ", ".join(sorted(severe)),
            )
            _add_once(
                suppressions,
                "title risk suppresses escalation",
            )

    if opportunity.status in {
        "INSUFFICIENT_IDENTITY",
        "INSUFFICIENT_SOLD_COMPS",
        "HIGH_RISK",
    }:
        _add_once(
            suppressions,
            opportunity.status,
        )

    if not looks:
        _add_once(
            looks,
            "no defensible sold-value discount detected",
        )

    positive_edge = max(edge_pct or 0.0, 0.0)
    edge_score = min(positive_edge, 60.0) / 60.0 * 25.0
    identity_score = (
        max(0.0, min(opportunity.identity_confidence, 1.0)) * 15.0
    )
    sold_score = _sold_evidence_score(valuation)

    active_score = 0.0
    if cross_store_reference is not None:
        discount = cross_store_reference.candidate_discount_to_median_pct
        if (
            cross_store_reference.status
            == MarketReferenceStatus.REFERENCE_AVAILABLE
            and discount is not None
            and discount > 0
            and cross_store_reference.consensus_strength > 0
        ):
            raw_active_score = min(discount, 40.0) / 40.0 * 5.0
            active_score = (
                raw_active_score
                * min(cross_store_reference.consensus_strength, 1.0)
            )

    history_score = 0.0
    history_penalty = 0.0
    if (
        listing_history is not None
        and valuation.status == "VALUED"
        and positive_edge > 0
    ):
        if listing_history.is_new:
            history_score += 2.0
        if listing_history.is_price_drop:
            history_score += min(
                abs(listing_history.price_change_pct or 0.0),
                30.0,
            ) / 30.0 * 4.0

        history_score = min(history_score, 6.0)

        if listing_history.is_stale:
            history_penalty += 4.0
        if listing_history.price_drop_count >= 2:
            history_penalty += 3.0

    risk_penalty = min(opportunity.risk_score * 0.45, 35.0)
    dispersion_penalty = 0.0
    if spread_pct is not None and spread_pct >= 60.0:
        dispersion_penalty = min((spread_pct - 60.0) / 4.0, 15.0)

    score = max(
        0.0,
        min(
            100.0,
            edge_score
            + identity_score
            + sold_score
            + active_score
            + history_score
            - risk_penalty
            - dispersion_penalty
            - history_penalty
            - underdescription_penalty,
        ),
    )

    if valuation.status != "VALUED":
        score = min(score, 25.0)
    if opportunity.status == "INSUFFICIENT_IDENTITY":
        score = min(score, 10.0)
    if opportunity.status == "HIGH_RISK":
        score = min(score, 35.0)
    if positive_edge <= 0:
        score = min(score, 30.0)

    return MispricingAssessment(
        score=round(score, 2),
        why_it_looks_cheap=tuple(looks),
        why_it_may_be_cheap=tuple(may_be),
        evidence_flags=tuple(evidence),
        suppressions=tuple(suppressions),
    )
