from __future__ import annotations

import time
from dataclasses import dataclass

from .comp_key import broad_comp_query, comp_quality, exact_comp_query
from .config import settings
from .db import save_market_match, save_market_metrics, upsert_market_listing
from .market_matching import assess_match
from .market_metrics import calculate_active_metrics
from .models import ActiveMarketMetrics, Listing, MarketListing, MarketMatch, MatchLevel
from .sources.ebay import EbaySource


MIN_MARKET_IDENTITY_QUALITY = 0.70


@dataclass
class MarketScanResult:
    listing: Listing
    exact_query: str | None
    broad_query: str | None
    identity_quality: float
    metrics: ActiveMarketMetrics
    matches: list[MarketMatch]
    market_listings: list[MarketListing]


class MarketEngine:
    def __init__(
        self,
        market_source: EbaySource | None = None,
        cache_hours: float | None = None,
        max_queries: int | None = None,
        results_per_query: int | None = None,
    ):
        self.market_source = market_source or EbaySource()
        self.cache_seconds = float(
            settings.market_cache_hours if cache_hours is None else cache_hours
        ) * 3600
        self.max_queries = int(
            settings.max_market_queries_per_run if max_queries is None else max_queries
        )
        self.results_per_query = int(
            settings.ebay_results_per_query if results_per_query is None else results_per_query
        )
        self._query_cache: dict[str, tuple[float, list[MarketListing]]] = {}
        self.query_count = 0

    def _search(
        self,
        sport: str,
        query: str,
    ) -> list[MarketListing]:
        normalized = " ".join(query.split())
        now = time.time()

        cached = self._query_cache.get(normalized.lower())
        if cached and now - cached[0] <= self.cache_seconds:
            return cached[1]

        if self.query_count >= self.max_queries:
            raise RuntimeError(
                f"MAX_MARKET_QUERIES_PER_RUN reached ({self.max_queries})"
            )

        self.query_count += 1
        listings = self.market_source.search_market(
            sport=sport,
            query=normalized,
            limit=self.results_per_query,
        )
        self._query_cache[normalized.lower()] = (now, listings)

        return listings

    def scan_listing(
        self,
        listing: Listing,
        scan_run_id: int | None = None,
    ) -> MarketScanResult:
        identity = listing.identity
        quality = comp_quality(identity) if identity else 0.0
        exact_query = exact_comp_query(identity) if identity else None
        broad_query = broad_comp_query(identity) if identity else None

        if not identity or quality < MIN_MARKET_IDENTITY_QUALITY:
            metrics = ActiveMarketMetrics(
                source_listing_external_id=listing.external_id,
                status="INSUFFICIENT_IDENTITY",
            )
            save_market_metrics(metrics, scan_run_id)
            return MarketScanResult(
                listing=listing,
                exact_query=exact_query,
                broad_query=broad_query,
                identity_quality=quality,
                metrics=metrics,
                matches=[],
                market_listings=[],
            )

        market_listings: list[MarketListing] = []
        matches: list[MarketMatch] = []

        if exact_query:
            market_listings.extend(self._search(listing.sport, exact_query))

        matches = self._assess_and_store(
            listing=listing,
            market_listings=market_listings,
            scan_run_id=scan_run_id,
        )

        accepted = [
            match
            for match in matches
            if match.match_level in {MatchLevel.EXACT, MatchLevel.STRONG}
        ]

        if not accepted and broad_query and broad_query != exact_query:
            existing_keys = {
                (market.source, market.external_id)
                for market in market_listings
            }

            for market in self._search(listing.sport, broad_query):
                key = (market.source, market.external_id)
                if key not in existing_keys:
                    market_listings.append(market)
                    existing_keys.add(key)

            matches = self._assess_and_store(
                listing=listing,
                market_listings=market_listings,
                scan_run_id=scan_run_id,
            )

        metrics = calculate_active_metrics(
            source_listing_external_id=listing.external_id,
            cherry_price_aud=listing.price + listing.shipping,
            market_listings=market_listings,
            matches=matches,
        )
        save_market_metrics(metrics, scan_run_id)

        return MarketScanResult(
            listing=listing,
            exact_query=exact_query,
            broad_query=broad_query,
            identity_quality=quality,
            metrics=metrics,
            matches=matches,
            market_listings=market_listings,
        )

    def _assess_and_store(
        self,
        listing: Listing,
        market_listings: list[MarketListing],
        scan_run_id: int | None,
    ) -> list[MarketMatch]:
        matches: list[MarketMatch] = []

        for market_listing in market_listings:
            upsert_market_listing(market_listing)

            if not listing.identity or not market_listing.identity:
                assessment_level = MatchLevel.REJECT
                match = MarketMatch(
                    source_listing_external_id=listing.external_id,
                    market_source=market_listing.source,
                    market_external_id=market_listing.external_id,
                    match_level=assessment_level,
                    match_score=0.0,
                    match_reasons=[],
                    rejection_reasons=["missing parsed identity"],
                    risk_flags=market_listing.risk_flags,
                )
            else:
                assessment = assess_match(
                    listing.identity,
                    market_listing.identity,
                    market_listing.risk_flags,
                )
                match = MarketMatch(
                    source_listing_external_id=listing.external_id,
                    market_source=market_listing.source,
                    market_external_id=market_listing.external_id,
                    match_level=assessment.match_level,
                    match_score=assessment.match_score,
                    match_reasons=assessment.match_reasons,
                    rejection_reasons=assessment.rejection_reasons,
                    risk_flags=market_listing.risk_flags,
                )

            save_market_match(match, scan_run_id)
            matches.append(match)

        return matches
