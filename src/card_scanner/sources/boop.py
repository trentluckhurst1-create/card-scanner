from __future__ import annotations

import re
from typing import Final

import httpx
from bs4 import BeautifulSoup

from ..identity import parse_identity
from ..models import CardIdentity, Listing


BASE_URL: Final[str] = "https://www.boopcollectables.com.au"
COLLECTION_BY_SPORT: Final[dict[str, str]] = {
    "NBA": "nba-singles",
    "NFL": "nfl-singles",
    "AFL": "afl-singles",
}

SEALED_RE = re.compile(
    r"\b(?:hobby|mega|blaster|value|retail|display|booster|break|factory|collector|fat)\s+(?:box|pack|case|tin)\b|"
    r"\b(?:box|case)\s+of\s+\d+\b|"
    r"\bsealed\s+(?:box|pack|case|tin)\b|"
    r"\b(?:hobby|retail)\s+pack\b",
    re.IGNORECASE,
)

# Boop's short Shopify titles frequently omit the catalogue number while the
# product description contains it. Only explicit labels are trusted; naked
# numbers are deliberately ignored so print-run, anniversary and grade values
# can never be promoted into card identity.
DESCRIPTION_CARD_NUMBER_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"\bcard\s*(?:#|no\.?\s*|number\s*[:#]?\s*)([A-Z0-9][A-Z0-9\-.]*\d[A-Z0-9\-.]*)\b(?!\s*/)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:card\s+)?no\.?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-.]*\d[A-Z0-9\-.]*)\b(?!\s*/)",
        re.IGNORECASE,
    ),
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


class BoopSource:
    name = "boop"
    source_name = "boop"

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

    @staticmethod
    def _recover_identity_from_product(
        identity: CardIdentity,
        *,
        product: dict,
    ) -> CardIdentity:
        if identity.card_number:
            return identity

        body_html = str(product.get("body_html") or "")
        if not body_html.strip():
            return identity

        description = BeautifulSoup(body_html, "html.parser").get_text(" ", strip=True)
        for pattern in DESCRIPTION_CARD_NUMBER_PATTERNS:
            match = pattern.search(description)
            if not match:
                continue
            card_number = match.group(1).strip().upper()
            if card_number:
                return identity.model_copy(update={"card_number": card_number})

        return identity

    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        sport = sport.upper().strip()
        handle = COLLECTION_BY_SPORT.get(sport)
        if handle is None:
            return []

        limit = max(1, min(int(limit), 250))
        query_norm = query.strip().casefold()
        listings: list[Listing] = []
        seen: set[str] = set()
        page_size = 250

        for page in range(1, 8):
            response = self.client.get(
                f"{BASE_URL}/collections/{handle}/products.json",
                params={"limit": page_size, "page": page},
            )
            response.raise_for_status()
            products = response.json().get("products") or []
            if not isinstance(products, list):
                raise RuntimeError("Boop response did not contain a products list")
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

                identity = self._recover_identity_from_product(
                    parse_identity(title, sport),
                    product=product,
                )
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
                        seller="Boop Collectables",
                        condition="Raw / Store Listing",
                        identity=identity,
                    )
                )
                if len(listings) >= limit:
                    return listings

            if len(products) < page_size:
                break

        return listings
