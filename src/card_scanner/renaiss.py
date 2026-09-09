from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Any

import httpx

from .fx import RbaFxProvider
from .identity import parse_identity
from .models import CardIdentity, SoldComp
from .providers import SoldCompProvider


class RenaissSoldCompProvider(SoldCompProvider):
    """
    Ephemeral challenger provider using the public Renaiss Index API.

    Governance:
    - No account or API key.
    - API responses remain in memory only.
    - Search results are discovery candidates, never valuation evidence.
    - Only rows with kind=transaction become SoldComp candidates.
    - kind=listing rows are never sold evidence.
    - Structured Renaiss identity is used to select an item before trades
      are requested.
    - The scanner's existing strict sold-comp matcher remains authoritative.
    """

    name = "renaiss"
    persistence_allowed = False
    raw_response_persistence_allowed = False

    SEARCH_URL = "https://api.renaissos.com/v1/search"
    BASE_URL = "https://api.renaissos.com"

    def __init__(
        self,
        client: httpx.Client | Any | None = None,
        fx_provider: Any | None = None,
    ):
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CARD-SCANNER/1.0",
                "Accept": "application/json",
            },
        )
        self.fx_provider = (
            fx_provider
            if fx_provider is not None
            else (RbaFxProvider() if client is None else None)
        )

        self._search_cache: dict[str, list[dict[str, Any]]] = {}
        self._trade_cache: dict[str, list[dict[str, Any]]] = {}
        self.query_count = 0

    @staticmethod
    def _same_text(left: str | None, right: str | None) -> bool:
        if not left or not right:
            return False

        def norm(value: str) -> str:
            return re.sub(r"[^a-z0-9]+", "", value.lower())

        return norm(left) == norm(right)

    @staticmethod
    def _grade_number(value: Any) -> float | None:
        if value is None:
            return None

        match = re.search(r"(?<!\d)(10|[1-9])(?:\.([05]))?(?!\d)", str(value))
        if not match:
            return None

        fraction = match.group(2)
        return float(match.group(1) + (("." + fraction) if fraction else ""))

    @staticmethod
    def _sale_date(value: Any) -> str | None:
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
            return datetime.fromisoformat(
                text.replace("Z", "+00:00")
            ).date().isoformat()
        except ValueError:
            return None

    @staticmethod
    def _price_usd(row: dict[str, Any]) -> float | None:
        cents = row.get("priceUsdCents")
        if cents is None:
            return None

        try:
            cents_value = int(cents)
        except (TypeError, ValueError):
            return None

        if cents_value <= 0:
            return None

        return cents_value / 100.0

    @staticmethod
    def _transaction_id(row: dict[str, Any]) -> str:
        detail = str(row.get("detail") or "").strip()

        if detail:
            return detail

        material = "|".join(
            [
                str(row.get("observedAt") or ""),
                str(row.get("priceUsdCents") or ""),
                str(row.get("source") or ""),
                str(row.get("company") or ""),
                str(row.get("grade") or ""),
            ]
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _structured_title(item: dict[str, Any]) -> str:
        parts: list[str] = []

        for key in ("name", "setName"):
            value = str(item.get(key) or "").strip()
            if value:
                parts.append(value)

        card_number = str(item.get("cardNumber") or "").strip()
        if card_number:
            parts.append(f"#{card_number}")

        variation = str(item.get("variation") or "").strip()
        if variation:
            parts.append(variation)

        company = str(item.get("company") or "").strip()
        grade_label = str(item.get("gradeLabel") or "").strip()
        grade = str(item.get("grade") or "").strip()

        if grade_label:
            parts.append(grade_label)
        elif company or grade:
            parts.extend(value for value in (company, grade) if value)

        return " ".join(parts).strip()

    def _search(self, query: str) -> list[dict[str, Any]]:
        normalized = " ".join(query.split()).strip().lower()

        cached = self._search_cache.get(normalized)
        if cached is not None:
            return list(cached)

        self.query_count += 1
        response = self.client.get(
            self.SEARCH_URL,
            params={"q": query},
        )
        response.raise_for_status()
        payload = response.json()

        rows = payload.get("results", [])
        if not isinstance(rows, list):
            raise RuntimeError("Renaiss returned an unexpected search payload.")

        clean = [row for row in rows if isinstance(row, dict)]
        self._search_cache[normalized] = list(clean)
        return clean

    def _trades(self, href: str, limit: int) -> list[dict[str, Any]]:
        cache_key = href

        cached = self._trade_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        safe_limit = max(1, min(int(limit), 100))
        url = self.BASE_URL + href.rstrip("/") + "/trades"

        self.query_count += 1
        response = self.client.get(
            url,
            params={"limit": safe_limit},
        )
        response.raise_for_status()
        payload = response.json()

        rows = payload.get("trades", [])
        if not isinstance(rows, list):
            raise RuntimeError("Renaiss returned an unexpected trades payload.")

        clean = [row for row in rows if isinstance(row, dict)]
        self._trade_cache[cache_key] = list(clean)
        return clean

    def _item_matches_target(
        self,
        item: dict[str, Any],
        target: CardIdentity,
    ) -> bool:
        if str(item.get("game") or "").strip().lower() != "sports":
            return False

        if target.player:
            name = str(item.get("name") or "").strip()
            if not self._same_text(target.player, name):
                return False

        target_product = target.set_name or target.brand
        item_product = str(item.get("setName") or "").strip()

        if target_product:
            if not item_product:
                return False

            left = re.sub(r"[^a-z0-9]+", "", target_product.lower())
            right = re.sub(r"[^a-z0-9]+", "", item_product.lower())

            if left not in right and right not in left:
                return False

        if target.card_number:
            item_number = str(item.get("cardNumber") or "").strip()
            if not item_number or not self._same_text(
                target.card_number,
                item_number,
            ):
                return False

        if target.parallel:
            variation = str(item.get("variation") or "").strip()
            if not variation:
                return False

            left = re.sub(r"[^a-z0-9]+", "", target.parallel.lower())
            right = re.sub(r"[^a-z0-9]+", "", variation.lower())

            if left not in right and right not in left:
                return False

        if target.grader:
            company = str(item.get("company") or "").strip()
            if not self._same_text(target.grader, company):
                return False

        if target.grade is not None:
            item_grade = self._grade_number(
                item.get("gradeLabel") or item.get("grade")
            )
            if item_grade is None or float(target.grade) != item_grade:
                return False

        return True

    def sold_comps_for_identity(
        self,
        sport: str,
        identity: CardIdentity,
        query: str,
        limit: int = 50,
    ) -> list[SoldComp]:
        if sport.upper() not in {"NFL", "NBA", "MLB", "AFL"}:
            return []

        normalized_query = " ".join(query.split()).strip()
        if not normalized_query:
            return []

        search_rows = self._search(normalized_query)

        matching_items = [
            item
            for item in search_rows
            if self._item_matches_target(item, identity)
        ]

        comps: list[SoldComp] = []
        seen_ids: set[str] = set()

        for item in matching_items:
            href = str(item.get("href") or "").strip()
            if not href.startswith("/card/sports/"):
                continue

            title = self._structured_title(item)
            if not title:
                continue

            trades = self._trades(href, limit)

            for row in trades:
                if str(row.get("kind") or "").strip().lower() != "transaction":
                    continue

                sold_date = self._sale_date(row.get("observedAt"))
                price = self._price_usd(row)

                if not sold_date or price is None:
                    continue

                sale_id = self._transaction_id(row)
                if sale_id in seen_ids:
                    continue

                seen_ids.add(sale_id)

                sold_price_aud = None
                fx_note = None

                if self.fx_provider is not None:
                    conversion = self.fx_provider.convert_to_aud(
                        price,
                        "USD",
                        sold_date,
                    )
                    sold_price_aud = conversion.aud_amount
                    fx_note = (
                        f"FX_STATUS={conversion.status};"
                        f"FX_SOURCE={conversion.source};"
                        f"FX_RATE_DATE={conversion.rate_date or ''}"
                    )

                comps.append(
                    SoldComp(
                        source="renaiss_transaction",
                        sale_id=sale_id,
                        sold_date=sold_date,
                        title=title,
                        sold_price=price,
                        currency="USD",
                        shipping=0.0,
                        sold_price_aud=sold_price_aud,
                        sale_type="transaction",
                        url=None,
                        notes=(
                            "EPHEMERAL_PUBLIC_API;"
                            "KIND=TRANSACTION;"
                            "LISTING_ROWS_EXCLUDED=TRUE;"
                            "PERSISTENCE_ALLOWED=FALSE"
                            + (f";{fx_note}" if fx_note else "")
                        ),
                        identity=parse_identity(title, sport.upper()),
                    )
                )

        return comps

    def sold_comps(
        self,
        sport: str,
        query: str,
        limit: int = 50,
    ) -> list[SoldComp]:
        """
        Generic SoldCompProvider entry point.

        Renaiss requires structured target identity to prevent remote search
        noise from selecting the wrong card. Therefore generic query-only
        access deliberately returns no valuation evidence.
        """
        return []