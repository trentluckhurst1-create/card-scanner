from __future__ import annotations

from typing import Final

import httpx

from ..identity import parse_identity
from ..models import Listing


COLLECTION_BY_SPORT: Final[dict[str, str]] = {
    "NBA": "nba-singles",
    "NFL": "nfl-singles",
}

BASE_URL: Final[str] = "https://urbanempirecollectables.com"


class UrbanEmpireSource:
    source_name = "urbanempire"

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
        sport = sport.upper().strip()

        handle = COLLECTION_BY_SPORT.get(sport)

        if handle is None:
            return []

        limit = max(1, min(int(limit), 250))

        url = (
            f"{BASE_URL}/collections/"
            f"{handle}/products.json"
        )

        page_size = 250
        max_pages = 20
        page = 1

        listings: list[Listing] = []
        seen_ids: set[str] = set()

        while len(listings) < limit and page <= max_pages:
            response = self.client.get(
                url,
                params={
                    "limit": page_size,
                    "page": page,
                },
            )
            response.raise_for_status()

            payload = response.json()
            products = payload.get("products", [])

            if not isinstance(products, list):
                raise RuntimeError(
                    "Urban Empire response did not contain "
                    "a products list."
                )

            if not products:
                break

            for product in products:
                title = " ".join(
                    str(
                        product.get("title") or ""
                    ).split()
                )

                if not title:
                    continue

                if (
                    query
                    and query.casefold()
                    not in title.casefold()
                ):
                    continue

                variants = product.get("variants") or []

                if not variants:
                    continue

                available_variants = [
                    variant
                    for variant in variants
                    if bool(
                        variant.get(
                            "available",
                            False,
                        )
                    )
                ]

                if not available_variants:
                    continue

                variant = available_variants[0]

                try:
                    price = float(
                        variant.get("price") or 0.0
                    )
                except (TypeError, ValueError):
                    continue

                if price <= 0:
                    continue

                handle_value = str(
                    product.get("handle") or ""
                ).strip()

                product_id = str(
                    product.get("id") or ""
                ).strip()

                if not handle_value or not product_id:
                    continue

                if product_id in seen_ids:
                    continue

                seen_ids.add(product_id)

                images = product.get("images") or []
                image_url = None

                if images:
                    image_url = images[0].get("src")

                listings.append(
                    Listing(
                        source=self.source_name,
                        external_id=product_id,
                        url=(
                            f"{BASE_URL}/products/"
                            f"{handle_value}"
                        ),
                        title=title,
                        sport=sport,
                        price=price,
                        currency="AUD",
                        shipping=0.0,
                        image_url=image_url,
                        seller=(
                            "Urban Empire Collectables"
                        ),
                        condition="Raw / Store Listing",
                        identity=parse_identity(
                            title,
                            sport,
                        ),
                    )
                )

                if len(listings) >= limit:
                    break

            if len(products) < page_size:
                break

            page += 1

        return listings[:limit]
