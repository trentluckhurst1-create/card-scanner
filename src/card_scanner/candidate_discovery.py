from __future__ import annotations

from dataclasses import dataclass

from .comp_key import comp_quality
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
        identity is not None
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
