from __future__ import annotations

from dataclasses import dataclass

from .candidate_discovery import CandidateDiscoveryAssessment
from .listing_history import ListingHistoryAssessment
from .market_reference import CrossStoreReference, MarketReferenceStatus
from .underdescription import UnderdescriptionAssessment


@dataclass(frozen=True)
class ResearchPriorityAssessment:
    score: float
    priority: str
    reasons: tuple[str, ...]
    cautions: tuple[str, ...]
    active_reference_signal: bool
    history_signal: bool
    underdescription_signal: bool

    @property
    def can_create_buy(self) -> bool:
        return False

    @property
    def can_create_strong_buy(self) -> bool:
        return False

    @property
    def fair_value_aud(self) -> None:
        return None


def _add_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def assess_research_priority(
    discovery: CandidateDiscoveryAssessment,
    cross_store_reference: CrossStoreReference | None = None,
    listing_history: ListingHistoryAssessment | None = None,
    underdescription: UnderdescriptionAssessment | None = None,
) -> ResearchPriorityAssessment:
    """
    Rank listings for human research only.

    Identity determines whether a listing is researchable. Evidence determines
    whether it deserves CHECK or CHECK_FIRST priority. This layer cannot create
    fair value, BUY, or STRONG_BUY. Active asks are corroborative research
    context only. Genuine sold evidence remains the valuation authority.
    """

    reasons: list[str] = []
    cautions: list[str] = []

    if discovery.discovery_status == "SKIP":
        return ResearchPriorityAssessment(
            score=0.0,
            priority="SKIP",
            reasons=(),
            cautions=("DISCOVERY_SKIP",),
            active_reference_signal=False,
            history_signal=False,
            underdescription_signal=False,
        )

    # Identity is intentionally a minority of the score. A clean title makes a
    # card eligible for research, but must not by itself escalate to CHECK.
    score = max(0.0, min(float(discovery.discovery_score), 100.0)) * 0.30

    if discovery.sold_comp_ready:
        score += 8.0
        _add_once(reasons, "IDENTITY_READY_FOR_STRICT_COMP_RESEARCH")
    else:
        score -= 18.0
        _add_once(cautions, "IDENTITY_NOT_READY_FOR_STRICT_COMP_RESEARCH")

    quality = max(0.0, min(float(discovery.identity_quality), 1.0))
    score += quality * 6.0

    active_signal = False

    if (
        cross_store_reference is not None
        and cross_store_reference.status
        == MarketReferenceStatus.REFERENCE_AVAILABLE
    ):
        discount = cross_store_reference.candidate_discount_to_median_pct

        if discount is not None and discount > 0:
            active_signal = True
            bounded_discount = min(float(discount), 40.0)
            score += bounded_discount / 40.0 * 24.0
            _add_once(reasons, "BELOW_CROSS_STORE_ACTIVE_MEDIAN")

        source_count = len(cross_store_reference.reference_sources)

        if source_count >= 2:
            score += min(source_count, 4) / 4.0 * 6.0
            _add_once(reasons, "MULTI_SOURCE_ACTIVE_REFERENCE")

        if cross_store_reference.active_mad_pct is not None:
            mad = float(cross_store_reference.active_mad_pct)
            if mad <= 15.0:
                score += 4.0
                _add_once(reasons, "TIGHT_ACTIVE_REFERENCE_DISPERSION")
            elif mad >= 40.0:
                score -= 7.0
                _add_once(cautions, "WIDE_ACTIVE_REFERENCE_DISPERSION")

    history_signal = False
    strong_history_signal = False

    if listing_history is not None:
        if listing_history.is_price_drop:
            history_signal = True
            strong_history_signal = True
            score += 14.0
            _add_once(reasons, "OBSERVED_PRICE_DROP")

            drop = listing_history.latest_price_drop_pct
            if drop is not None:
                magnitude = abs(float(drop))
                score += min(magnitude, 30.0) / 30.0 * 8.0

        if listing_history.is_new:
            history_signal = True
            score += 3.0
            _add_once(reasons, "NEW_LISTING")

        if listing_history.is_relisted:
            history_signal = True
            score += 2.0
            _add_once(reasons, "RELISTED")

        if listing_history.is_stale:
            score -= 5.0
            _add_once(cautions, "STALE_LISTING")

        if listing_history.observation_count <= 1:
            _add_once(cautions, "SPARSE_HISTORY")

    under_signal = False
    under = underdescription or discovery.underdescription

    if under is not None:
        if under.status == "NOT_APPLICABLE":
            return ResearchPriorityAssessment(
                score=0.0,
                priority="SKIP",
                reasons=tuple(reasons),
                cautions=tuple(cautions + ["NON_CARD_OR_NOT_APPLICABLE"]),
                active_reference_signal=active_signal,
                history_signal=history_signal,
                underdescription_signal=False,
            )

        if under.status == "REVIEW":
            under_signal = True
            score += 5.0
            _add_once(reasons, "UNDERDESCRIPTION_REVIEW")

        if under.risk_score >= 0.70:
            score -= 12.0
            _add_once(cautions, "HIGH_UNDERDESCRIPTION_RISK")
        elif under.risk_score >= 0.40:
            score -= 5.0
            _add_once(cautions, "MODERATE_UNDERDESCRIPTION_RISK")

    score = max(0.0, min(score, 100.0))

    strong_evidence_count = int(active_signal) + int(strong_history_signal)

    # Priority has evidence gates as well as numeric thresholds. This prevents
    # clean identity alone from producing CHECK/CHECK_FIRST.
    if (
        discovery.sold_comp_ready
        and score >= 75.0
        and strong_evidence_count >= 2
    ):
        priority = "CHECK_FIRST"
    elif (
        discovery.sold_comp_ready
        and score >= 55.0
        and strong_evidence_count >= 1
    ):
        priority = "CHECK"
    elif discovery.sold_comp_ready and score >= 30.0:
        priority = "WATCH"
    else:
        priority = "LOW_PRIORITY"

    if discovery.sold_comp_ready and strong_evidence_count == 0:
        _add_once(cautions, "NO_STRONG_CORROBORATING_EVIDENCE")

    return ResearchPriorityAssessment(
        score=round(score, 6),
        priority=priority,
        reasons=tuple(reasons),
        cautions=tuple(cautions),
        active_reference_signal=active_signal,
        history_signal=history_signal,
        underdescription_signal=under_signal,
    )


def research_priority_sort_key(
    assessment: ResearchPriorityAssessment,
) -> tuple:
    rank = {
        "CHECK_FIRST": 0,
        "CHECK": 1,
        "WATCH": 2,
        "LOW_PRIORITY": 3,
        "SKIP": 4,
    }

    return (
        rank.get(assessment.priority, 9),
        -assessment.score,
    )
