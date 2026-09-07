from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from .comp_key import comp_quality
from .models import Listing, Opportunity, SoldValuation
from .opportunity import assess_opportunity
from .risk import title_risk_details
from .sold_comp_engine import (
    EphemeralSoldCompEngine,
    MIN_SOLD_COMP_IDENTITY_QUALITY,
)
from .the_card_api import TheCardApiSoldCompProvider


SPORTS = ("NFL", "NBA", "MLB", "AFL")


class CherrySearchSource(Protocol):
    def search(
        self,
        sport: str,
        query: str = "",
        limit: int = 50,
    ) -> list[Listing]:
        ...


@dataclass(frozen=True)
class OpportunityScanResult:
    listing: Listing
    identity_quality: float
    player_query: str | None
    exact_query: str | None
    broad_query: str | None
    fetched_count: int
    accepted_count: int
    exact_count: int
    strong_count: int
    rejected_count: int
    sold_queries_used: int
    valuation: SoldValuation
    opportunity: Opportunity


@dataclass(frozen=True)
class OpportunityScanSummary:
    results: list[OpportunityScanResult]
    candidates_considered: int
    candidates_scanned: int
    sold_queries_used: int
    query_budget: int
    budget_remaining: int
    valued_count: int
    buy_count: int
    strong_buy_count: int
    watch_count: int
    fair_count: int
    overpriced_count: int
    insufficient_comps_count: int
    insufficient_identity_count: int
    high_risk_count: int
    fetched_listings: int


def _identity_richness(listing: Listing) -> int:
    identity = listing.identity

    if identity is None:
        return 0

    score = 0

    if identity.player:
        score += 3
    if identity.year:
        score += 2
    if identity.set_name or identity.brand:
        score += 2
    if identity.parallel:
        score += 2
    if identity.serial_total is not None:
        score += 2
    if identity.card_number:
        score += 1
    if identity.rookie:
        score += 1
    if identity.autograph:
        score += 1
    if identity.memorabilia:
        score += 1
    if identity.grader:
        score += 1
    if identity.grade is not None:
        score += 1

    return score


def candidate_priority(listing: Listing) -> tuple:
    identity = listing.identity
    quality = comp_quality(identity) if identity else 0.0

    has_identity = int(identity is not None)
    has_player = int(bool(identity and identity.player))

    comp_ready = int(
        has_identity
        and has_player
        and quality >= MIN_SOLD_COMP_IDENTITY_QUALITY
    )

    return (
        -comp_ready,
        -has_player,
        -quality,
        -_identity_richness(listing),
        listing.sport.upper(),
        listing.title.casefold(),
        str(listing.external_id),
    )


def _status_count(
    results: list[OpportunityScanResult],
    status: str,
) -> int:
    return sum(
        1
        for result in results
        if result.opportunity.status == status
    )


def scan_cherry_opportunities(
    cherry_source: CherrySearchSource,
    sold_provider=None,
    sport: str = "ALL",
    listings_per_sport: int = 50,
    max_candidates_per_sport: int = 10,
    sold_results_per_query: int = 100,
    max_sold_queries: int = 80,
    as_of: date | None = None,
) -> OpportunityScanSummary:
    """
    Run an ephemeral Cherry -> sold comps -> valuation -> opportunity scan.

    The Card API sale rows, sold matches, valuations and opportunities created
    by this function remain in memory only.
    """

    sport = sport.upper()

    if sport == "ALL":
        sports = list(SPORTS)
    elif sport in SPORTS:
        sports = [sport]
    else:
        raise ValueError(
            f"Unsupported sport: {sport}. "
            "Expected NFL, NBA, MLB, AFL or ALL."
        )

    listings_per_sport = max(1, int(listings_per_sport))
    max_candidates_per_sport = max(
        0,
        int(max_candidates_per_sport),
    )
    sold_results_per_query = max(
        1,
        int(sold_results_per_query),
    )
    max_sold_queries = max(
        0,
        int(max_sold_queries),
    )
    as_of = as_of or date.today()

    provider = (
        sold_provider
        if sold_provider is not None
        else TheCardApiSoldCompProvider()
    )

    results: list[OpportunityScanResult] = []

    fetched_listings = 0
    candidates_considered = 0
    candidates_scanned = 0
    sold_queries_used = 0
    insufficient_identity_count = 0

    for sport_name in sports:
        listings = cherry_source.search(
            sport_name,
            "",
            listings_per_sport,
        )

        fetched_listings += len(listings)

        ranked = sorted(
            listings,
            key=candidate_priority,
        )

        eligible: list[Listing] = []

        for listing in ranked:
            identity = listing.identity
            quality = comp_quality(identity) if identity else 0.0

            if (
                identity is None
                or not identity.player
                or quality < MIN_SOLD_COMP_IDENTITY_QUALITY
            ):
                insufficient_identity_count += 1
                continue

            eligible.append(listing)

        selected = eligible[:max_candidates_per_sport]
        candidates_considered += len(selected)

        for listing in selected:
            remaining = max_sold_queries - sold_queries_used

            # Existing sold engine can use up to two calls:
            # player recall + supplemental broad query.
            if remaining < 2:
                break

            if listing.identity is None:
                continue

            engine = EphemeralSoldCompEngine(
                provider=provider,
                results_per_query=sold_results_per_query,
            )

            sold_result = engine.scan_identity(
                source_listing_external_id=listing.external_id,
                sport=listing.sport,
                identity=listing.identity,
                as_of=as_of,
            )

            if sold_result.query_count > remaining:
                raise RuntimeError(
                    "Sold-comp engine exceeded opportunity scan query budget."
                )

            sold_queries_used += sold_result.query_count
            candidates_scanned += 1

            opportunity = assess_opportunity(
                listing,
                sold_result.valuation,
                title_risk_details(listing.title),
            )

            results.append(
                OpportunityScanResult(
                    listing=listing,
                    identity_quality=sold_result.identity_quality,
                    player_query=sold_result.player_query,
                    exact_query=sold_result.exact_query,
                    broad_query=sold_result.broad_query,
                    fetched_count=sold_result.fetched_count,
                    accepted_count=sold_result.accepted_count,
                    exact_count=sold_result.exact_count,
                    strong_count=sold_result.strong_count,
                    rejected_count=sold_result.rejected_count,
                    sold_queries_used=sold_result.query_count,
                    valuation=sold_result.valuation,
                    opportunity=opportunity,
                )
            )

    valued_count = sum(
        1
        for result in results
        if result.valuation.status == "VALUED"
    )

    return OpportunityScanSummary(
        results=results,
        candidates_considered=candidates_considered,
        candidates_scanned=candidates_scanned,
        sold_queries_used=sold_queries_used,
        query_budget=max_sold_queries,
        budget_remaining=max_sold_queries - sold_queries_used,
        valued_count=valued_count,
        buy_count=_status_count(results, "BUY"),
        strong_buy_count=_status_count(results, "STRONG_BUY"),
        watch_count=_status_count(results, "WATCH"),
        fair_count=_status_count(results, "FAIR"),
        overpriced_count=_status_count(results, "OVERPRICED"),
        insufficient_comps_count=_status_count(
            results,
            "INSUFFICIENT_SOLD_COMPS",
        ),
        insufficient_identity_count=insufficient_identity_count,
        high_risk_count=_status_count(results, "HIGH_RISK"),
        fetched_listings=fetched_listings,
    )


_STATUS_ORDER = {
    "STRONG_BUY": 0,
    "BUY": 1,
    "WATCH": 2,
    "FAIR": 3,
    "OVERPRICED": 4,
    "HIGH_RISK": 5,
    "INSUFFICIENT_SOLD_COMPS": 6,
    "INSUFFICIENT_IDENTITY": 7,
}


def opportunity_result_sort_key(
    result: OpportunityScanResult,
) -> tuple:
    opportunity = result.opportunity

    status_rank = _STATUS_ORDER.get(
        opportunity.status,
        99,
    )

    if opportunity.status in {"BUY", "STRONG_BUY"}:
        secondary = -float(
            opportunity.opportunity_score or 0.0
        )
    elif opportunity.edge_pct is not None:
        secondary = -float(opportunity.edge_pct)
    else:
        secondary = -float(result.identity_quality)

    return (
        status_rank,
        secondary,
        result.listing.sport.upper(),
        result.listing.title.casefold(),
        str(result.listing.external_id),
    )
