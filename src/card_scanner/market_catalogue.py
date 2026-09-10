from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .listing_history import ListingHistoryAssessment, get_listing_history
from .models import Listing
from .opportunity_scanner import MultiStoreCollection, MultiStoreSource


@dataclass(frozen=True)
class MarketListingObservation:
    listing: Listing
    history: ListingHistoryAssessment | None = None


class _SearchSource(Protocol):
    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        ...


class CapturingStoreSource:
    """Transparent single-store wrapper that records fetched listings in memory."""

    def __init__(self, source: _SearchSource) -> None:
        self.source = source
        self.captured: list[Listing] = []

    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        rows = self.source.search(sport, query, limit)
        self.captured.extend(rows)
        return rows


class CapturingMultiStoreSource(MultiStoreSource):
    """Multi-store source preserving isinstance checks while capturing scan pools."""

    def __init__(self, source: MultiStoreSource) -> None:
        super().__init__(source.stores)
        self.captured: list[Listing] = []

    def collect(
        self,
        sport: str,
        query: str = "",
        limit: int = 50,
    ) -> MultiStoreCollection:
        collection = super().collect(sport, query, limit)
        self.captured.extend(collection.listings)
        return collection


def capture_store_source(source):
    if isinstance(source, MultiStoreSource):
        return CapturingMultiStoreSource(source)
    return CapturingStoreSource(source)


def catalogue_observations(
    source,
    *,
    include_history: bool,
) -> list[MarketListingObservation]:
    """Return one safe observation per captured source/external-id pair.

    The capture layer performs no extra store HTTP calls. When history is enabled,
    assessments are read from the already-persisted lawful active-listing state.
    """

    deduped: dict[tuple[str, str], Listing] = {}
    for listing in source.captured:
        key = (listing.source.casefold(), str(listing.external_id))
        deduped[key] = listing

    observations: list[MarketListingObservation] = []
    for listing in deduped.values():
        history = (
            get_listing_history(listing.source, listing.external_id)
            if include_history
            else None
        )
        observations.append(MarketListingObservation(listing=listing, history=history))

    observations.sort(
        key=lambda row: (
            row.listing.sport.upper(),
            row.listing.source.casefold(),
            row.listing.title.casefold(),
            str(row.listing.external_id),
        )
    )
    return observations
