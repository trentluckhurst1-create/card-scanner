from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .models import CardIdentity, Listing


class MarketReferenceStatus(str, Enum):
    NO_REFERENCE = "NO_REFERENCE"
    INSUFFICIENT_REFERENCE = "INSUFFICIENT_REFERENCE"
    REFERENCE_AVAILABLE = "REFERENCE_AVAILABLE"


@dataclass(frozen=True)
class MarketReferencePoint:
    source: str
    external_id: str
    url: str
    price_aud: float
    shipping_aud: float
    landed_aud: float
    title: str
    identity: CardIdentity
    match_level: str


@dataclass(frozen=True)
class CrossStoreReference:
    candidate_source: str
    candidate_external_id: str
    candidate_landed_aud: float
    matched_listing_count: int
    exact_match_count: int
    strong_match_count: int
    source_count: int
    reference_sources: tuple[str, ...]
    reference_prices_aud: tuple[float, ...]
    min_reference_price_aud: float | None
    median_reference_price_aud: float | None
    max_reference_price_aud: float | None
    candidate_discount_to_median_pct: float | None
    confidence: float
    status: MarketReferenceStatus


class MarketReferenceProvider(Protocol):
    name: str

    def find_references(
        self,
        candidate: Listing,
    ) -> list[Listing]:
        ...