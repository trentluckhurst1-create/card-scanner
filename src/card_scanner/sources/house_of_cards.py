from __future__ import annotations

import html as html_lib
import re
from typing import Final

import httpx

from ..identity import parse_identity
from ..models import Listing

BASE_URL: Final[str] = "https://www.houseofcardsnco.com.au"
SUPPORTED_SPORTS: Final[set[str]] = {"AFL", "NBA", "NFL", "MLB"}
SEALED_TERMS: Final[tuple[str, ...]] = (
    "box",
    "pack",
    "case",
    "break",
    "bundle",
    "tin",
    "blaster",
    "mega",
    "hobby box",
    "display",
)
PRODUCT_LINK_RE = re.compile(r'href=["\'](?:https?://www\.houseofcardsnco\.com\.au)?(/product/[^"\'?#]+)', re.I)
H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
PRICE_RE = re.compile(r"(?:A\$|\$)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
OG_IMAGE_RE = re.compile(
    r'<meta\b[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
    re.I,
)
TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value: str) -> str:
    return " ".join(html_lib.unescape(TAG_RE.sub(" ", value)).split())


def _is_single_card_title(title: str) -> bool:
    low = title.casefold()
    return not any(re.search(rf"\b{re.escape(term)}\b", low) for term in SEALED_TERMS)


class HouseOfCardsSource:
    """Targeted House of Cards sports-single discovery.

    The public shop is heavily mixed between singles and sealed inventory, so this
    source intentionally performs targeted searches only, follows product pages,
    and fails closed unless a listing has strong parsed card identity.
    """

    name = "houseofcards"
    source_name = "houseofcards"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._external_client = client is not None
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )

    def close(self) -> None:
        if not self._external_client:
            self.client.close()

    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        sport = sport.upper().strip()
        if sport not in SUPPORTED_SPORTS:
            return []

        query = " ".join(query.split())
        # The all-products page is mixed and client-rendered. Broad crawling would
        # pull sealed inventory, so only targeted player/card searches are allowed.
        if not query:
            return []

        limit = max(1, min(int(limit), 100))
        response = self.client.get(f"{BASE_URL}/shop", params={"q": query})
        response.raise_for_status()

        product_paths: list[str] = []
        seen_paths: set[str] = set()
        for match in PRODUCT_LINK_RE.finditer(response.text):
            path = match.group(1)
            if path in seen_paths:
                continue
            seen_paths.add(path)
            product_paths.append(path)
            if len(product_paths) >= max(12, min(limit * 3, 60)):
                break

        output: list[Listing] = []
        for path in product_paths:
            product_url = f"{BASE_URL}{path}"
            product = self.client.get(product_url)
            product.raise_for_status()
            page = product.text

            # Active-market feed must not contain unavailable asks.
            if re.search(r"\bsold\s+out\b", _clean_text(page), flags=re.I):
                continue

            title_match = H1_RE.search(page)
            if not title_match:
                continue
            title = _clean_text(title_match.group(1))
            if not title or not _is_single_card_title(title):
                continue

            query_terms = [part.casefold() for part in query.split() if len(part) >= 2]
            title_low = title.casefold()
            if query_terms and not all(term in title_low for term in query_terms):
                continue

            price_match = PRICE_RE.search(_clean_text(page))
            if not price_match:
                continue
            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue

            identity = parse_identity(title, sport)
            if not identity.player or not identity.year:
                continue
            # Exact comparison candidates need a card number, or a serial print run
            # plus named parallel. Anything weaker stays out rather than guessing.
            if not identity.card_number and not (identity.serial_total and identity.parallel):
                continue

            image_match = OG_IMAGE_RE.search(page)
            image_url = html_lib.unescape(image_match.group(1)) if image_match else None
            external_id = path.rsplit("/", 1)[-1]
            output.append(
                Listing(
                    source=self.source_name,
                    external_id=external_id,
                    url=product_url,
                    title=title,
                    sport=sport,
                    price=price,
                    currency="AUD",
                    shipping=0.0,
                    image_url=image_url,
                    seller="House of Cards N Collectables",
                    condition="Store Listing",
                    identity=identity,
                )
            )
            if len(output) >= limit:
                break

        return output
