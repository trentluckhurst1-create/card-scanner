from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from .models import Listing


RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class SearchSource(Protocol):
    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        ...


def is_retryable_store_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))


@dataclass
class RetryingStoreSource:
    """Cloud-safe bounded retry wrapper for transient store failures only.

    Hard client errors such as 401/403/404 are never retried. This wrapper does
    not alter listing parsing, identity matching, pricing, or valuation logic.
    """

    source: SearchSource
    attempts: int = 3
    base_delay_seconds: float = 0.4

    @property
    def name(self) -> str | None:
        return getattr(self.source, "name", None) or getattr(self.source, "source_name", None)

    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        attempts = max(1, int(self.attempts))
        for attempt in range(1, attempts + 1):
            try:
                return self.source.search(sport=sport, query=query, limit=limit)
            except Exception as exc:
                if attempt >= attempts or not is_retryable_store_error(exc):
                    raise
                delay = max(0.0, float(self.base_delay_seconds)) * attempt
                if delay:
                    time.sleep(delay)
        raise RuntimeError("Retry loop exited unexpectedly")
