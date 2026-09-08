from __future__ import annotations

from dataclasses import dataclass

from .cross_store_reference import build_cross_store_reference
from .market_reference import CrossStoreReference
from .models import Listing
from .opportunity_scanner import NamedStoreSource


@dataclass(frozen=True)
class CrossStoreSearchResult:
    reference: CrossStoreReference
    stores_considered: int
    stores_searched: int
    listings_fetched: int
    store_errors: tuple[str, ...]


class CrossStoreReferenceProvider:
    """
    Ephemeral active-market reference collector.

    Active asking prices are corroborative market context only.
    They are not sold comps and are not fair value.
    """

    name = "cross_store_active_market"

    def __init__(
        self,
        stores: list[NamedStoreSource],
        listings_per_store: int = 50,
    ) -> None:
        self.stores = list(stores)
        self.listings_per_store = max(
            1,
            int(listings_per_store),
        )

    def find_references(
        self,
        candidate: Listing,
    ) -> list[Listing]:
        return self.search(candidate).listings

    def search(
        self,
        candidate: Listing,
    ) -> "_CollectedReferences":
        references: list[Listing] = []
        stores_considered = 0
        stores_searched = 0
        errors: list[str] = []

        for store in self.stores:
            store_name = store.name.casefold()
            candidate_source = candidate.source.casefold()

            # Cross-store means other acquisition sources only.
            if store_name == candidate_source:
                continue

            stores_considered += 1

            try:
                listings = store.source.search(
                    candidate.sport,
                    "",
                    self.listings_per_store,
                )
            except Exception as exc:
                errors.append(
                    f"{store.name}: {type(exc).__name__}: {exc}"
                )
                continue

            stores_searched += 1
            references.extend(listings)

        return _CollectedReferences(
            listings=references,
            stores_considered=stores_considered,
            stores_searched=stores_searched,
            store_errors=tuple(errors),
        )

    def assess(
        self,
        candidate: Listing,
    ) -> CrossStoreSearchResult:
        collected = self.search(candidate)

        return self.assess_from_pool(
            candidate,
            collected.listings,
            stores_considered=collected.stores_considered,
            stores_searched=collected.stores_searched,
            store_errors=collected.store_errors,
        )

    def assess_from_pool(
        self,
        candidate: Listing,
        listings: list[Listing],
        *,
        stores_considered: int = 0,
        stores_searched: int = 0,
        store_errors: tuple[str, ...] = (),
    ) -> CrossStoreSearchResult:
        reference = build_cross_store_reference(
            candidate,
            listings,
        )

        return CrossStoreSearchResult(
            reference=reference,
            stores_considered=stores_considered,
            stores_searched=stores_searched,
            listings_fetched=len(listings),
            store_errors=store_errors,
        )


@dataclass(frozen=True)
class _CollectedReferences:
    listings: list[Listing]
    stores_considered: int
    stores_searched: int
    store_errors: tuple[str, ...]