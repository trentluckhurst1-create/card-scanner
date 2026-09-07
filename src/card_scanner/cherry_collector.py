from __future__ import annotations

from dataclasses import dataclass, field

from .config import settings
from .db import (
    finish_scan_run,
    mark_missing_listings,
    recent_successful_scan,
    save_cherry_scan_summary,
    start_scan_run,
    upsert_inventory_listing,
)
from .sources.cherry import CherrySource
from .watchlist import record_listing_watch_events


@dataclass
class CherryScanSummary:
    sport: str
    scan_run_id: int | None = None
    fetched: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    price_drops: int = 0
    price_rises: int = 0
    missing: int = 0
    inactive: int = 0
    errors: int = 0
    skipped_cache: bool = False
    error_messages: list[str] = field(default_factory=list)

    def as_counts(self) -> dict[str, int]:
        return {
            "fetched": self.fetched,
            "new": self.new,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "price_drops": self.price_drops,
            "price_rises": self.price_rises,
            "missing": self.missing,
            "inactive": self.inactive,
            "errors": self.errors,
        }


class CherryCollector:
    def __init__(
        self,
        source: CherrySource | None = None,
        page_size: int | None = None,
        max_products_per_sport: int | None = None,
        cache_minutes: float | None = None,
        missing_scan_threshold: int | None = None,
    ):
        self.source = source or CherrySource()
        self.page_size = int(page_size or settings.cherry_page_size)
        self.max_products_per_sport = int(
            max_products_per_sport or settings.cherry_max_products_per_sport
        )
        self.cache_minutes = float(
            settings.cherry_scan_cache_minutes if cache_minutes is None else cache_minutes
        )
        self.missing_scan_threshold = int(
            missing_scan_threshold or settings.cherry_missing_scan_threshold
        )

    def scan_sport(
        self,
        sport: str,
        force: bool = False,
    ) -> CherryScanSummary:
        sport = sport.upper()
        summary = CherryScanSummary(sport=sport)

        if (
            not force
            and self.cache_minutes > 0
            and recent_successful_scan("cherry", sport, self.cache_minutes)
        ):
            summary.skipped_cache = True
            return summary

        scan_run_id = start_scan_run("cherry", sport)
        summary.scan_run_id = scan_run_id
        observed: set[str] = set()
        page = 1

        try:
            while summary.fetched < self.max_products_per_sport:
                products = self.source._fetch_page(
                    sport=sport,
                    page=page,
                    page_size=self.page_size,
                )

                if not products:
                    break

                for product in products:
                    if summary.fetched >= self.max_products_per_sport:
                        break

                    try:
                        listing = self.source.product_to_listing(product, sport)
                    except ValueError:
                        continue
                    except Exception as exc:
                        summary.errors += 1
                        summary.error_messages.append(str(exc))
                        continue

                    if listing.external_id in observed:
                        continue

                    observed.add(listing.external_id)
                    summary.fetched += 1
                    event_type = upsert_inventory_listing(listing, scan_run_id)
                    record_listing_watch_events(listing, event_type)

                    if event_type == "NEW_LISTING":
                        summary.new += 1
                    elif event_type == "PRICE_DROP":
                        summary.price_drops += 1
                    elif event_type == "PRICE_RISE":
                        summary.price_rises += 1
                    elif event_type in {"UPDATED", "RELISTED"}:
                        summary.updated += 1
                    elif event_type == "UNCHANGED":
                        summary.unchanged += 1

                if len(products) < self.page_size:
                    break

                page += 1

            missing_counts = mark_missing_listings(
                source="cherry",
                sport=sport,
                observed_external_ids=observed,
                scan_run_id=scan_run_id,
                missing_threshold=self.missing_scan_threshold,
            )
            summary.missing = missing_counts["missing"]
            summary.inactive = missing_counts["inactive"]
            status = "PASS" if summary.errors == 0 else "PARTIAL"
            finish_scan_run(
                scan_run_id,
                status,
                "; ".join(summary.error_messages[:5]) or None,
            )
        except Exception as exc:
            summary.errors += 1
            summary.error_messages.append(str(exc))
            finish_scan_run(scan_run_id, "FAILED", str(exc))
            raise
        finally:
            if summary.scan_run_id:
                save_cherry_scan_summary(
                    summary.scan_run_id,
                    sport,
                    summary.as_counts(),
                )

        return summary
