from __future__ import annotations

import re
from typing import Final

import httpx

from ..identity import parse_identity
from ..models import Listing


BASE_URL: Final[str] = "https://thehobby.com.au"
COLLECTION_BY_SPORT: Final[dict[str, str]] = {
    "AFL": "afl",
    "NBA": "nba",
    "NFL": "nfl",
    "MLB": "baseball-cards",
}

# Sport collections include both singles and sealed inventory. The cloud
# comparison feed must contain individual cards only, so reject obvious sealed
# products conservatively rather than trying to value/compare them as singles.
SEALED_RE = re.compile(
    r"\b(?:hobby|mega|blaster|value|retail|display|booster|break|factory|collector|fat)\s+(?:box|pack|case|tin)\b|"
    r"\b(?:box|case)\s+of\s+\d+\b|"
    r"\b\d+[- ]box\s+case\b|"
    r"\bsealed\s+(?:box|pack|case|tin)\b|"
    r"\b(?:hobby|retail)\s+pack\b",
    re.IGNORECASE,
)


def _money(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _image_url(product: dict) -> str | None:
    images = product.get("images") or []
    if images:
        src = images[0].get("src")
        if src:
            return str(src)
    image = product.get("image")
    if isinstance(image, dict) and image.get("src"):
        return str(image["src"])
    return None


class TheHobbySource:
    name = "thehobby"
    source_name = "thehobby"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._external_client = client is not None
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152.0 Safari/537.36",
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-AU,en;q=0.9",
            },
        )

    def close(self) -> None:
        if not self._external_client:
            self.client.close()

    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        sport = sport.upper().strip()
        handle = COLLECTION_BY_SPORT.get(sport)
        if handle is None:
            return []

        limit = max(1, min(int(limit), 250))
        page_size = 250
        query_norm = query.strip().casefold()
        listings: list[Listing] = []
        seen: set[str] = set()

        # A collection page can contain sealed products before singles. Walk a
        # bounded number of Shopify pages so the requested singles depth can be
        # filled without unbounded crawling.
        for page in range(1, 13):
            response = self.client.get(
                f"{BASE_URL}/collections/{handle}/products.json",
                params={"limit": page_size, "page": page},
            )
            response.raise_for_status()
            products = response.json().get("products") or []
            if not isinstance(products, list):
                raise RuntimeError("The Hobby response did not contain a products list")
            if not products:
                break

            for product in products:
                title = " ".join(str(product.get("title") or "").split())
                if not title or SEALED_RE.search(title):
                    continue
                if query_norm and query_norm not in title.casefold():
                    continue

                variants = product.get("variants") or []
                available = [v for v in variants if bool(v.get("available", False))]
                if not available:
                    continue
                price = _money(available[0].get("price"))
                if price <= 0:
                    continue

                handle_value = str(product.get("handle") or "").strip()
                product_id = str(product.get("id") or handle_value).strip()
                if not handle_value or not product_id or product_id in seen:
                    continue
                seen.add(product_id)

                identity = parse_identity(title, sport)
                # A valid single must at minimum parse a player and year. This
                # is a guard against collection contamination such as supplies,
                # generic sealed products, or non-card merchandise.
                if not identity.player or not identity.year:
                    continue

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
                        image_url=_image_url(product),
                        seller="The Hobby Australia",
                        condition="Raw / Store Listing",
                        identity=identity,
                    )
                )
                if len(listings) >= limit:
                    return listings

            if len(products) < page_size:
                break

        return listings
