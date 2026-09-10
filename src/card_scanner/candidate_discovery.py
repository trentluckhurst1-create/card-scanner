from __future__ import annotations

from dataclasses import dataclass

from .comp_key import comp_quality, identity_signature
from .listing_history import ListingHistoryAssessment
from .models import Listing
from .sold_comp_engine import MIN_SOLD_COMP_IDENTITY_QUALITY
from .underdescription import (
    UnderdescriptionAssessment,
    assess_underdescription,
)


@dataclass(frozen=True)
class CandidateDiscoveryAssessment:
    listing: Listing
    discovery_score: float
    discovery_status: str
    identity_quality: float
    identity_richness: int
    sold_comp_ready: bool
    investigation_reasons: tuple[str, ...]
    caution_reasons: tuple[str, ...]
    underdescription: UnderdescriptionAssessment
    listing_history: ListingHistoryAssessment | None = None

    @property
    def can_create_buy(self) -> bool:
        return False

    @property
    def fair_value_aud(self) -> None:
        return None


def _identity_richness(listing: Listing) -> int:
    identity = listing.identity
    if identity is None:
        return 0

    values = (
        identity.player,
        identity.year,
        identity.brand,
        identity.set_name,
        identity.card_number,
        identity.parallel,
        identity.serial_total,
        identity.grader,
        identity.grade,
    )

    score = sum(value is not None and value != "" for value in values)
    score += int(identity.rookie)
    score += int(identity.autograph)
    score += int(identity.memorabilia)
    return score


def _add_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def assess_candidate_discovery(
    listing: Listing,
    listing_history: ListingHistoryAssessment | None = None,
) -> CandidateDiscoveryAssessment:
    identity = listing.identity
    quality = comp_quality(identity) if identity is not None else 0.0
    richness = _identity_richness(listing)

    under = assess_underdescription(listing)

    sold_ready = bool(
        under.status != "NOT_APPLICABLE"
        and identity is not None
        and identity.player
        and quality >= MIN_SOLD_COMP_IDENTITY_QUALITY
    )

    score = 0.0
    reasons: list[str] = []
    cautions: list[str] = []

    if sold_ready:
        score += 35.0
        _add_once(reasons, "SOLD_COMP_READY_IDENTITY")
    elif identity is not None and identity.player:
        score += 12.0
        _add_once(cautions, "IDENTITY_BELOW_SOLD_THRESHOLD")
    else:
        _add_once(cautions, "PLAYER_IDENTITY_MISSING")

    score += max(0.0, min(quality, 1.0)) * 25.0
    score += min(richness, 10) / 10.0 * 10.0

    if under.status == "CLEAR":
        score += 8.0
        _add_once(reasons, "TITLE_IDENTITY_CLEAR")
    elif under.status == "REVIEW":
        score += 4.0
        _add_once(reasons, "UNDERDESCRIPTION_REVIEW_SIGNAL")
        _add_once(cautions, "TITLE_REQUIRES_REVIEW")
    elif under.status == "POOR":
        score -= 12.0
        _add_once(cautions, "POOR_TITLE_IDENTITY")
    elif under.status == "NOT_APPLICABLE":
        score = 0.0
        _add_once(cautions, "NON_CARD_PRODUCT")

    if under.risk_score >= 0.70:
        score -= 15.0
        _add_once(cautions, "HIGH_UNDERDESCRIPTION_RISK")
    elif under.risk_score >= 0.40:
        score -= 6.0
        _add_once(cautions, "MODERATE_UNDERDESCRIPTION_RISK")

    if listing_history is not None:
        if listing_history.is_price_drop:
            score += 10.0
            _add_once(reasons, "RECENT_PRICE_DROP")

        drop = listing_history.latest_price_drop_pct
        if drop is not None:
            magnitude = abs(float(drop))
            score += min(magnitude, 30.0) / 30.0 * 7.0

        if listing_history.is_new:
            score += 4.0
            _add_once(reasons, "NEW_LISTING")

        if listing_history.is_relisted:
            score += 3.0
            _add_once(reasons, "RELISTED")

        if listing_history.is_stale:
            score -= 3.0
            _add_once(cautions, "STALE_LISTING")

    score = max(0.0, min(score, 100.0))

    if under.status == "NOT_APPLICABLE":
        status = "SKIP"
    elif not sold_ready:
        status = "LOW_PRIORITY"
    elif score >= 75.0:
        status = "INVESTIGATE_FIRST"
    elif score >= 55.0:
        status = "INVESTIGATE"
    else:
        status = "LOW_PRIORITY"

    return CandidateDiscoveryAssessment(
        listing=listing,
        discovery_score=round(score, 6),
        discovery_status=status,
        identity_quality=quality,
        identity_richness=richness,
        sold_comp_ready=sold_ready,
        investigation_reasons=tuple(reasons),
        caution_reasons=tuple(cautions),
        underdescription=under,
        listing_history=listing_history,
    )


def candidate_discovery_sort_key(
    assessment: CandidateDiscoveryAssessment,
) -> tuple:
    status_rank = {
        "INVESTIGATE_FIRST": 0,
        "INVESTIGATE": 1,
        "LOW_PRIORITY": 2,
        "SKIP": 3,
    }

    return (
        status_rank.get(assessment.discovery_status, 9),
        -assessment.discovery_score,
        -assessment.identity_quality,
        assessment.listing.sport.upper(),
        assessment.listing.title.casefold(),
        str(assessment.listing.external_id),
    )


def rank_candidates(
    listings: list[Listing],
    histories: dict[tuple[str, str], ListingHistoryAssessment] | None = None,
) -> list[CandidateDiscoveryAssessment]:
    history_map = histories or {}

    assessments = [
        assess_candidate_discovery(
            listing,
            history_map.get((listing.source, str(listing.external_id))),
        )
        for listing in listings
    ]

    return sorted(assessments, key=candidate_discovery_sort_key)
@dataclass(frozen=True)
class CandidateResearchFamily:
    """
    One valuation identity family competing for sold-research budget.

    The family key uses the existing canonical identity_signature().
    Serial numerator is intentionally excluded by that signature while
    serial denominator, parallel, grade and other valuation attributes
    remain identity-bearing.

    Asking price is research-allocation context only. It is never fair
    value and cannot create BUY.
    """

    family_key: str
    representative: CandidateDiscoveryAssessment
    member_count: int
    lowest_landed_aud: float
    allocation_score: float

    @property
    def can_create_buy(self) -> bool:
        return False

    @property
    def fair_value_aud(self) -> None:
        return None


def _listing_landed_aud_for_research(listing: Listing) -> float:
    """
    Research-only capital-at-risk proxy.

    Candidate Discovery currently operates on AU store listings. This
    helper deliberately does not perform FX conversion and must not be
    used as valuation evidence.
    """

    if listing.currency.upper() != "AUD":
        return float("inf")

    return max(0.0, float(listing.price) + float(listing.shipping or 0.0))


def _capital_efficiency_points(landed_aud: float) -> float:
    """
    Small bounded research-priority bonus only.

    Lower capital at risk can justify spending scarce sold-comp research
    earlier, but price alone must never dominate identity quality.
    """

    if landed_aud <= 25.0:
        return 8.0
    if landed_aud <= 50.0:
        return 7.0
    if landed_aud <= 100.0:
        return 6.0
    if landed_aud <= 200.0:
        return 4.0
    if landed_aud <= 500.0:
        return 2.0
    if landed_aud <= 1000.0:
        return 1.0
    return 0.0


def candidate_research_families(
    assessments: list[CandidateDiscoveryAssessment],
) -> list[CandidateResearchFamily]:
    """
    Collapse sold-comp-ready candidates to canonical valuation families.

    This function allocates research attention only. It does not value
    cards, consume sold evidence, weaken matching, or create BUY.
    """

    grouped: dict[str, list[CandidateDiscoveryAssessment]] = {}

    for assessment in assessments:
        if not assessment.sold_comp_ready:
            continue

        if assessment.discovery_status == "SKIP":
            continue

        identity = assessment.listing.identity
        if identity is None:
            continue

        key = identity_signature(identity)
        if not key:
            continue

        grouped.setdefault(key, []).append(assessment)

    families: list[CandidateResearchFamily] = []

    for key, members in grouped.items():
        ordered = sorted(
            members,
            key=lambda row: (
                _listing_landed_aud_for_research(row.listing),
                candidate_discovery_sort_key(row),
            ),
        )

        representative = ordered[0]
        lowest_landed = _listing_landed_aud_for_research(
            representative.listing
        )

        allocation_score = min(
            100.0,
            representative.discovery_score
            + _capital_efficiency_points(lowest_landed),
        )

        families.append(
            CandidateResearchFamily(
                family_key=key,
                representative=representative,
                member_count=len(members),
                lowest_landed_aud=lowest_landed,
                allocation_score=allocation_score,
            )
        )

    families.sort(
        key=lambda family: (
            -family.allocation_score,
            -family.representative.identity_quality,
            family.lowest_landed_aud,
            family.family_key,
        )
    )

    return families


def allocate_research_candidates(
    assessments: list[CandidateDiscoveryAssessment],
    limit: int,
) -> list[CandidateDiscoveryAssessment]:
    """
    Return at most one representative per canonical valuation family.
    """

    if limit <= 0:
        return []

    families = candidate_research_families(assessments)

    return [
        family.representative
        for family in families[:limit]
    ]
