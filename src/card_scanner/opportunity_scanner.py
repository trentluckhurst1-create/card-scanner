from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Protocol

from .candidate_discovery import (
    allocate_research_candidates,
    assess_candidate_discovery,
)
from .comp_key import comp_quality
from .listing_history import (
    ListingHistoryAssessment,
    ListingHistoryBatch,
    record_store_listing_observations,
)
from .market_reference import CrossStoreReference
from .models import Listing, Opportunity, SoldValuation
from .mispricing import MispricingAssessment, assess_mispricing
from .opportunity import assess_opportunity
from .risk import title_risk_details
from .sold_comp_engine import (
    EphemeralSoldCompEngine,
    MIN_SOLD_COMP_IDENTITY_QUALITY,
)
from .the_card_api import TheCardApiSoldCompProvider
from .underdescription import (
    UnderdescriptionAssessment,
    assess_underdescription,
)


SPORTS = ("NFL", "NBA", "MLB", "AFL")


from .research_priority import (
    ResearchPriorityAssessment,
    assess_research_priority,
)


class StoreSearchSource(Protocol):
    def search(
        self,
        sport: str,
        query: str = "",
        limit: int = 50,
    ) -> list[Listing]:
        ...


@dataclass(frozen=True)
class NamedStoreSource:
    name: str
    source: StoreSearchSource


@dataclass(frozen=True)
class MultiStoreCollection:
    listings: list[Listing]
    stores_considered: int
    stores_searched: int
    store_errors: tuple[str, ...]


class MultiStoreSource:
    def __init__(
        self,
        stores: list[NamedStoreSource],
    ) -> None:
        self.stores = list(stores)

    def search(
        self,
        sport: str,
        query: str = "",
        limit: int = 50,
    ) -> list[Listing]:
        return self.collect(
            sport,
            query,
            limit,
        ).listings

    def collect(
        self,
        sport: str,
        query: str = "",
        limit: int = 50,
    ) -> MultiStoreCollection:
        listings: list[Listing] = []
        errors: list[str] = []
        stores_searched = 0

        for store in self.stores:
            try:
                rows = store.source.search(
                    sport,
                    query,
                    limit,
                )
            except Exception as exc:
                errors.append(
                    f"{store.name}: {type(exc).__name__}: {exc}"
                )
                continue

            stores_searched += 1
            listings.extend(rows)

        return MultiStoreCollection(
            listings=listings,
            stores_considered=len(self.stores),
            stores_searched=stores_searched,
            store_errors=tuple(errors),
        )


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
    mispricing: MispricingAssessment | None = None
    listing_history: ListingHistoryAssessment | None = None
    underdescription: UnderdescriptionAssessment | None = None
    cross_store_reference: CrossStoreReference | None = None
    reference_rejection_summary: dict[str, int] | None = None
    research_priority: ResearchPriorityAssessment | None = None


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
    history_observed_count: int = 0
    history_new_count: int = 0
    history_unchanged_count: int = 0
    history_price_drop_count: int = 0
    history_price_increase_count: int = 0
    history_relisted_count: int = 0
    history_stale_count: int = 0
    history_event_count: int = 0
    history_errors: tuple[str, ...] = ()
    reference_store_errors: tuple[str, ...] = ()


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


def scan_store_opportunities(
    store_source: StoreSearchSource,
    sold_provider=None,
    sport: str = "ALL",
    listings_per_sport: int = 50,
    max_candidates_per_sport: int = 10,
    sold_results_per_query: int = 100,
    max_sold_queries: int = 80,
    as_of: date | None = None,
    record_history: bool = False,
    history_observed_at: datetime | None = None,
    history_stale_after_days: int | None = None,
) -> OpportunityScanSummary:
    """
    Run an ephemeral store -> sold comps -> valuation -> opportunity scan.

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
    reference_store_errors: list[str] = []
    history_observed_count = 0
    history_new_count = 0
    history_unchanged_count = 0
    history_price_drop_count = 0
    history_price_increase_count = 0
    history_relisted_count = 0
    history_stale_count = 0
    history_event_count = 0
    history_errors: list[str] = []

    for sport_name in sports:
        collection: MultiStoreCollection | None = None
        history_batch: ListingHistoryBatch | None = None

        if isinstance(store_source, MultiStoreSource):
            collection = store_source.collect(
                sport_name,
                "",
                listings_per_sport,
            )
            listings = collection.listings
            reference_store_errors.extend(collection.store_errors)
        else:
            listings = store_source.search(
                sport_name,
                "",
                listings_per_sport,
            )

        fetched_listings += len(listings)

        if record_history:
            history_batch = record_store_listing_observations(
                listings,
                observed_at=history_observed_at,
                stale_after_days=history_stale_after_days,
            )
            history_observed_count += history_batch.observed_count
            history_new_count += history_batch.state_created_count
            history_unchanged_count += history_batch.unchanged_count
            history_price_drop_count += history_batch.price_drop_count
            history_price_increase_count += history_batch.price_increase_count
            history_relisted_count += history_batch.relisted_count
            history_stale_count += history_batch.stale_count
            history_event_count += history_batch.event_count
            history_errors.extend(history_batch.errors)

        discovery_assessments = []

        for listing in listings:
            listing_history = (
                history_batch.histories.get(
                    (listing.source.casefold(), listing.external_id)
                )
                if history_batch is not None
                else None
            )

            discovery_assessments.append(
                assess_candidate_discovery(
                    listing,
                    listing_history,
                )
            )

        for discovery in discovery_assessments:
            if not discovery.sold_comp_ready:
                insufficient_identity_count += 1

        research_candidates = allocate_research_candidates(
            discovery_assessments,
            max_candidates_per_sport,
        )

        selected = [
            discovery.listing
            for discovery in research_candidates
        ]
        candidates_considered += len(selected)

        for listing in selected:
            remaining = max_sold_queries - sold_queries_used

            # The sold engine may use one player-recall call and,
            # only when budget permits, one supplemental broad call.
            if remaining < 1:
                break

            if listing.identity is None:
                continue

            listing_history = (
                history_batch.histories.get(
                    (listing.source.casefold(), listing.external_id)
                )
                if history_batch is not None
                else None
            )
            cross_store_reference = None
            reference_rejection_summary = None

            if collection is not None:
                from .cross_store_provider import CrossStoreReferenceProvider

                searched_sources = {
                    row.source.casefold()
                    for row in listings
                }

                reference_result = CrossStoreReferenceProvider(
                    stores=store_source.stores,
                    listings_per_store=listings_per_sport,
                ).assess_from_pool(
                    listing,
                    listings,
                    stores_considered=max(
                        0,
                        collection.stores_considered - 1,
                    ),
                    stores_searched=len(
                        searched_sources
                        - {listing.source.casefold()}
                    ),
                    store_errors=collection.store_errors,
                )
                cross_store_reference = reference_result.reference
                reference_rejection_summary = (
                    reference_result.rejection_summary
                )

            engine = EphemeralSoldCompEngine(
                provider=provider,
                results_per_query=sold_results_per_query,
            )

            sold_result = engine.scan_identity(
                source_listing_external_id=listing.external_id,
                sport=listing.sport,
                identity=listing.identity,
                as_of=as_of,
                max_queries=min(2, remaining),
            )

            if sold_result.query_count > remaining:
                raise RuntimeError(
                    "Sold-comp engine exceeded opportunity scan query budget."
                )

            sold_queries_used += sold_result.query_count
            candidates_scanned += 1

            risk_flags = title_risk_details(listing.title)
            underdescription = assess_underdescription(listing)
            opportunity = assess_opportunity(
                listing,
                sold_result.valuation,
                risk_flags,
            )
            mispricing = assess_mispricing(
                listing,
                sold_result.valuation,
                opportunity,
                risk_flags,
                cross_store_reference,
                listing_history,
                underdescription,
            )
            candidate_discovery = next(
                (
                    row
                    for row in research_candidates
                    if row.listing is listing
                ),
                None,
            )
            if candidate_discovery is None:
                raise RuntimeError(
                    "Selected listing lost its discovery assessment."
                )

            research_priority = assess_research_priority(
                candidate_discovery,
                cross_store_reference=cross_store_reference,
                listing_history=listing_history,
                underdescription=underdescription,
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
                    mispricing=mispricing,
                    listing_history=listing_history,
                    underdescription=underdescription,
                    cross_store_reference=cross_store_reference,
                    reference_rejection_summary=reference_rejection_summary,
                    research_priority=research_priority,
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
        history_observed_count=history_observed_count,
        history_new_count=history_new_count,
        history_unchanged_count=history_unchanged_count,
        history_price_drop_count=history_price_drop_count,
        history_price_increase_count=history_price_increase_count,
        history_relisted_count=history_relisted_count,
        history_stale_count=history_stale_count,
        history_event_count=history_event_count,
        history_errors=tuple(history_errors),
        reference_store_errors=tuple(reference_store_errors),
    )



def scan_cherry_opportunities(
    cherry_source: StoreSearchSource,
    sold_provider=None,
    sport: str = "ALL",
    listings_per_sport: int = 50,
    max_candidates_per_sport: int = 10,
    sold_results_per_query: int = 100,
    max_sold_queries: int = 80,
    as_of: date | None = None,
) -> OpportunityScanSummary:
    """Backward-compatible Cherry wrapper around the generic store scanner."""
    return scan_store_opportunities(
        store_source=cherry_source,
        sold_provider=sold_provider,
        sport=sport,
        listings_per_sport=listings_per_sport,
        max_candidates_per_sport=max_candidates_per_sport,
        sold_results_per_query=sold_results_per_query,
        max_sold_queries=max_sold_queries,
        as_of=as_of,
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

    if opportunity.status in {"STRONG_BUY", "BUY", "WATCH", "FAIR", "OVERPRICED"}:
        if result.mispricing is not None:
            secondary = -float(result.mispricing.score)
        elif opportunity.status in {"BUY", "STRONG_BUY"}:
            secondary = -float(opportunity.opportunity_score or 0.0)
        elif opportunity.edge_pct is not None:
            secondary = -float(opportunity.edge_pct)
        else:
            secondary = -float(result.identity_quality)
    elif result.research_priority is not None:
        secondary = -float(result.research_priority.score)
    elif result.mispricing is not None:
        secondary = -float(result.mispricing.score)
    else:
        secondary = -float(result.identity_quality)

    return (
        status_rank,
        secondary,
        result.listing.sport.upper(),
        result.listing.title.casefold(),
        str(result.listing.external_id),
    )
