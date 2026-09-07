from __future__ import annotations

from abc import ABC, abstractmethod

from .models import MarketListing, SoldComp, SoldValuation


class ActiveMarketProvider(ABC):
    @abstractmethod
    def search_market(
        self,
        sport: str,
        query: str,
        limit: int = 50,
    ) -> list[MarketListing]:
        raise NotImplementedError


class CurrentValueProvider(ABC):
    @abstractmethod
    def current_value(
        self,
        source_listing_external_id: str,
    ) -> SoldValuation:
        raise NotImplementedError


class SoldCompProvider(ABC):
    @abstractmethod
    def sold_comps(
        self,
        sport: str,
        query: str,
        limit: int = 50,
    ) -> list[SoldComp]:
        raise NotImplementedError


class NoAutomatedSoldCompProvider(SoldCompProvider):
    def sold_comps(
        self,
        sport: str,
        query: str,
        limit: int = 50,
    ) -> list[SoldComp]:
        return []
