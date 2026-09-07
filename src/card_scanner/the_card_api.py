from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from .config import settings
from .identity import parse_identity
from .models import SoldComp
from .providers import SoldCompProvider


class TheCardApiSoldCompProvider(SoldCompProvider):
    """
    Ephemeral sold-comp provider for The Card API free tier.

    IMPORTANT:
    - API responses are held in memory only.
    - This provider never writes sales to SQLite, JSON, CSV or disk cache.
    - `persistence_allowed` is intentionally False.
    - Free-tier use is evaluation / personal / non-commercial only.
    """

    name = "the_card_api"
    persistence_allowed = False
    raw_response_persistence_allowed = False

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        client: httpx.Client | Any | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.the_card_api_key
        self.base_url = (
            base_url
            if base_url is not None
            else settings.the_card_api_base_url
        )
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CARD-SCANNER/1.0",
                "Accept": "application/json",
            },
        )

        # Session-memory cache only. Never serialized.
        self._session_cache: dict[
            tuple[str, str, int],
            list[SoldComp],
        ] = {}

        self.query_count = 0

    def missing_credentials(self) -> list[str]:
        return [] if self.api_key.strip() else ["THE_CARD_API_KEY"]

    @staticmethod
    def _price(value: Any) -> float | None:
        if value is None:
            return None

        if isinstance(value, dict):
            value = (
                value.get("value")
                or value.get("amount")
                or value.get("price")
            )

        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None

        return parsed if parsed > 0 else None

    @staticmethod
    def _sale_date(row: dict[str, Any]) -> str | None:
        value = row.get("sale_date") or row.get("sold_at")

        if not value:
            return None

        text = str(value).strip()

        if len(text) >= 10:
            candidate = text[:10]
            try:
                date.fromisoformat(candidate)
                return candidate
            except ValueError:
                pass

        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.date().isoformat()
        except ValueError:
            return None

    @staticmethod
    def _is_confirmed(value: Any) -> bool:
        if value is True:
            return True

        if isinstance(value, str):
            return value.strip().lower() == "true"

        return False

    @staticmethod
    def _query_with_safety_terms(query: str) -> str:
        query = " ".join(query.split()).strip()

        negatives = [
            "-reprint",
            "-digital",
            "-custom",
            "-proxy",
        ]

        return " ".join([query, *negatives]).strip()

    def sold_comps(
        self,
        sport: str,
        query: str,
        limit: int = 50,
    ) -> list[SoldComp]:
        if not self.api_key.strip():
            raise RuntimeError(
                "Missing THE_CARD_API_KEY in local .env"
            )

        normalized_query = " ".join(query.split()).strip()

        if not normalized_query:
            return []

        safe_limit = max(1, min(int(limit), 1000))
        cache_key = (
            sport.upper(),
            normalized_query.lower(),
            safe_limit,
        )

        cached = self._session_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        params = {
            "q": self._query_with_safety_terms(normalized_query),
            "platform": "ebay",
            "category": "sports",
            "limit": safe_limit,
        }

        self.query_count += 1

        response = self.client.get(
            self.base_url,
            params=params,
            headers={
                "x-market-api-key": self.api_key,
            },
        )

        response.raise_for_status()
        payload = response.json()

        rows = payload.get("data", [])
        if not isinstance(rows, list):
            raise RuntimeError(
                "The Card API returned an unexpected data payload."
            )

        comps: list[SoldComp] = []
        seen_ids: set[str] = set()

        for row in rows:
            if not isinstance(row, dict):
                continue

            # Only confirmed completed eBay prices can influence valuation.
            if str(row.get("platform") or "").strip().lower() != "ebay":
                continue

            if not self._is_confirmed(row.get("price_confirmed")):
                continue

            title = str(row.get("title") or "").strip()
            sale_id = str(row.get("id") or "").strip()
            currency = str(row.get("currency") or "").strip().upper()
            sold_date = self._sale_date(row)
            price = self._price(row.get("price"))

            if (
                not title
                or not sale_id
                or not currency
                or not sold_date
                or price is None
            ):
                continue

            if sale_id in seen_ids:
                continue

            seen_ids.add(sale_id)

            # The Card API documents eBay `price` as the buyer price.
            # Do not add shipping again.
            sold_price_aud = price if currency == "AUD" else None

            comps.append(
                SoldComp(
                    source="the_card_api_ebay",
                    sale_id=sale_id,
                    sold_date=sold_date,
                    title=title,
                    sold_price=price,
                    currency=currency,
                    shipping=0.0,
                    sold_price_aud=sold_price_aud,
                    sale_type=(
                        str(row.get("listing_type") or "").strip()
                        or None
                    ),
                    url=(
                        str(row.get("listing_url") or "").strip()
                        or None
                    ),
                    notes=(
                        "EPHEMERAL_FREE_TIER;"
                        "PRICE_CONFIRMED=TRUE;"
                        "PERSISTENCE_ALLOWED=FALSE"
                    ),
                    identity=parse_identity(title, sport.upper()),
                )
            )

        # Memory-only cache.
        self._session_cache[cache_key] = list(comps)

        return comps
