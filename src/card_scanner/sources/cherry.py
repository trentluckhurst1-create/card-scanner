from __future__ import annotations

import httpx

from card_scanner.identity import parse_identity
from card_scanner.models import Listing
from .base import ListingSource


COLLECTIONS = {
    "NFL": "nfl-singles",
    "NBA": "nba-singles",
    "MLB": "mlb-singles",
    "AFL": "afl-singles",
}

BASE_URL = "https://www.cherrycollectables.com.au"
SHOPIFY_PAGE_SIZE = 250


def _money(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _image_url(product: dict) -> str | None:
    images = product.get("images") or []
    if images:
        src = images[0].get("src")
        if src:
            return src

    image = product.get("image")
    if isinstance(image, dict):
        return image.get("src")

    return None


def _variant_price(product: dict) -> tuple[float, bool]:
    variants = product.get("variants") or []

    if not variants:
        return 0.0, False

    available_variants = [
        v for v in variants
        if bool(v.get("available", False))
    ]

    chosen = available_variants[0] if available_variants else variants[0]

    return _money(chosen.get("price")), bool(chosen.get("available", False))


class CherrySource(ListingSource):
    name = "cherry"

    def __init__(self):
        self.client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 CardScannerV1",
                "Accept": "application/json",
            },
            follow_redirects=True,
            timeout=30,
        )
        # A publisher run may issue many player-specific overlap searches over
        # the same collection. Cache Shopify pages for this source instance so
        # each page is fetched at most once per run.
        self._page_cache: dict[tuple[str, int, int], list[dict]] = {}

    def _collection_url(self, sport: str) -> str:
        sport = sport.upper()

        if sport not in COLLECTIONS:
            raise ValueError(
                f"Unsupported Cherry sport: {sport}. "
                f"Supported: {', '.join(COLLECTIONS)}"
            )

        handle = COLLECTIONS[sport]

        return (
            f"{BASE_URL}/collections/"
            f"{handle}/products.json"
        )

    def _fetch_page(
        self,
        sport: str,
        page: int,
        page_size: int,
    ) -> list[dict]:
        sport = sport.upper()
        cache_key = (sport, int(page), int(page_size))
        cached = self._page_cache.get(cache_key)
        if cached is not None:
            return cached

        response = self.client.get(
            self._collection_url(sport),
            params={
                "limit": page_size,
                "page": page,
            },
        )

        response.raise_for_status()

        payload = response.json()

        products = payload.get("products") or []

        if not isinstance(products, list):
            raise RuntimeError(
                "Cherry response did not contain a products list."
            )

        self._page_cache[cache_key] = products
        return products

    def product_to_listing(
        self,
        product: dict,
        sport: str,
    ) -> Listing:
        sport = sport.upper()
        title = " ".join(
            str(product.get("title", "")).split()
        )

        if not title:
            raise ValueError("Cherry product missing title")

        handle = str(product.get("handle", "")).strip()

        if not handle:
            raise ValueError("Cherry product missing handle")

        product_id = str(product.get("id", "")).strip()

        if not product_id:
            product_id = handle

        price, available = _variant_price(product)

        if not available:
            raise ValueError("Cherry product unavailable")

        if price <= 0:
            raise ValueError("Cherry product missing positive price")

        url = f"{BASE_URL}/products/{handle}"

        return Listing(
            source=self.name,
            external_id=product_id,
            url=url,
            title=title,
            sport=sport,
            price=price,
            currency="AUD",
            shipping=0.0,
            image_url=_image_url(product),
            seller="Cherry Collectables",
            condition="Raw / Store Listing",
            identity=parse_identity(
                title,
                sport,
            ),
        )

    def search(
        self,
        sport: str,
        query: str = "",
        limit: int = 50,
    ) -> list[Listing]:

        sport = sport.upper()
        limit = max(1, int(limit))

        query_normalized = query.strip().lower()

        results: list[Listing] = []

        page = 1

        # Shopify supports 250 products per page. Always use the maximum page
        # size even when the caller only wants a handful of matches; targeted
        # overlap searches otherwise walk dozens of 50-product pages.
        page_size = SHOPIFY_PAGE_SIZE

        while len(results) < limit:

            products = self._fetch_page(
                sport=sport,
                page=page,
                page_size=page_size,
            )

            if not products:
                break

            for product in products:
                try:
                    listing = self.product_to_listing(product, sport)
                except ValueError:
                    continue

                if (
                    query_normalized
                    and query_normalized not in listing.title.lower()
                ):
                    continue

                results.append(listing)

                if len(results) >= limit:
                    break

            if len(products) < page_size:
                break

            page += 1

            # Safety guard. With 250-item pages this is far beyond the current
            # Cherry singles inventory while still preventing unbounded crawls.
            if page > 24:
                break

        return results
