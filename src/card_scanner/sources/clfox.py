from __future__ import annotations

from typing import Final

import httpx

from ..identity import parse_identity
from ..models import Listing

BASE_URL: Final[str] = "https://clfoxcollectables.com"


class CLFoxSource:
    """Cloud-safe Shopify discovery source for CLFox basketball singles."""

    name = "clfox"
    source_name = "clfox"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._external_client = client is not None
        self.client = client or httpx.Client(timeout=30.0, follow_redirects=True)
        # Exact discovery can issue many player queries against the same Shopify
        # catalogue. Reuse each fetched page for the whole publisher run rather
        # than hammering products.json repeatedly and triggering 429 responses.
        self._page_cache: dict[int, list[dict]] = {}

    def close(self) -> None:
        if not self._external_client:
            self.client.close()

    def _fetch_page(self, page: int) -> list[dict]:
        cached = self._page_cache.get(int(page))
        if cached is not None:
            return cached
        response = self.client.get(
            f"{BASE_URL}/products.json",
            params={"limit": 250, "page": page},
        )
        response.raise_for_status()
        products = response.json().get("products") or []
        if not isinstance(products, list):
            raise RuntimeError("CLFox response did not contain a products list")
        self._page_cache[int(page)] = products
        return products

    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        if sport.upper().strip() != "NBA":
            return []
        limit = max(1, min(int(limit), 250))
        query_norm = query.strip().casefold()
        output: list[Listing] = []
        seen: set[str] = set()
        for page in range(1, 13):
            products = self._fetch_page(page)
            if not products:
                break
            for product in products:
                title = " ".join(str(product.get("title") or "").split())
                if not title or (query_norm and query_norm not in title.casefold()):
                    continue
                variants = [v for v in (product.get("variants") or []) if bool(v.get("available", False))]
                if not variants:
                    continue
                try:
                    price = float(variants[0].get("price") or 0)
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue
                identity = parse_identity(title, "NBA")
                if not identity.player:
                    continue
                product_id = str(product.get("id") or "")
                handle = str(product.get("handle") or "")
                if not product_id or not handle or product_id in seen:
                    continue
                seen.add(product_id)
                images = product.get("images") or []
                image_url = str(images[0].get("src")) if images and images[0].get("src") else None
                output.append(Listing(source=self.source_name, external_id=product_id, url=f"{BASE_URL}/products/{handle}", title=title, sport="NBA", price=price, currency="AUD", shipping=0.0, image_url=image_url, seller="CLFox Collectables", condition="Raw / Store Listing", identity=identity))
                if len(output) >= limit:
                    return output
            if len(products) < 250:
                break
        return output
