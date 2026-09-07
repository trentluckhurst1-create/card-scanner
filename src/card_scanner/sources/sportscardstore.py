from __future__ import annotations

from typing import Final

import httpx

from ..identity import parse_identity
from ..models import Listing


COLLECTION_BY_SPORT: Final[dict[str, str]] = {
    "AFL": "afl-singles",
    "NBA": "nba-singles",
}

BASE_URL: Final[str] = "https://sportscardstore.com.au"


class SportsCardStoreSource:
    source_name = "sportscardstore"

    def __init__(
        self,
        client: httpx.Client | None = None,
    ) -> None:
        self._external_client = client is not None
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": "card-scanner-v1/1.0",
            },
        )

    def close(self) -> None:
        if not self._external_client:
            self.client.close()

    def search(
        self,
        sport: str,
        query: str = "",
        limit: int = 50,
    ) -> list[Listing]:
        sport = sport.upper()

        handle = COLLECTION_BY_SPORT.get(sport)
        if handle is None:
            return []

        limit = max(1, min(int(limit), 250))

        url = (
            f"{BASE_URL}/collections/"
            f"{handle}/products.json"
        )

        response = self.client.get(
            url,
            params={"limit": limit},
        )
        response.raise_for_status()

        payload = response.json()
        products = payload.get("products", [])

        listings: list[Listing] = []

        for product in products:
            title = str(product.get("title") or "").strip()
            if not title:
                continue

            if query and query.casefold() not in title.casefold():
                continue

            variants = product.get("variants") or []
            if not variants:
                continue

            variant = variants[0]

            if not variant.get("available", False):
                continue

            try:
                price = float(variant.get("price") or 0.0)
            except (TypeError, ValueError):
                continue

            if price <= 0:
                continue

            handle_value = str(product.get("handle") or "").strip()
            product_id = str(product.get("id") or "").strip()

            if not handle_value or not product_id:
                continue

            images = product.get("images") or []
            image_url = None

            if images:
                image_url = images[0].get("src")

            listings.append(
                Listing(
                    source=self.source_name,
                    external_id=product_id,
                    url=f"{BASE_URL}/products/{handle_value}",
                    title=title,
                    sport=sport,
                    price=price,
                    currency="AUD",
                    shipping=0.0,
                    image_url=image_url,
                    seller="Sports Card Store Australia",
                    condition="Raw / Store Listing",
                    identity=parse_identity(title, sport),
                )
            )

        return listings[:limit]
