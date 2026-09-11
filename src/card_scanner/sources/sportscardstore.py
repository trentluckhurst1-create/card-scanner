from __future__ import annotations

import re
from typing import Final

import httpx
from bs4 import BeautifulSoup

from ..identity import parse_identity
from ..models import CardIdentity, Listing


COLLECTION_BY_SPORT: Final[dict[str, str]] = {
    "AFL": "afl-singles",
    "NBA": "nba-singles",
}

BASE_URL: Final[str] = "https://sportscardstore.com.au"

# Sports Card Store often puts the catalogue/card number in Shopify body_html
# even when the shorter storefront title omits it. Recovery remains deliberately
# strict: explicit card/no/number labels are preferred, x/y serial syntax is
# rejected, and the fallback only accepts a standalone all-caps team line.
DESCRIPTION_CARD_NUMBER_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"\bcard\s*(?:#|no\.?\s*|number\s*[:#]?\s*)([A-Z0-9][A-Z0-9\-.]*\d[A-Z0-9\-.]*)\b(?!\s*/)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:card\s+)?no\.?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-.]*\d[A-Z0-9\-.]*)\b(?!\s*/)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcard\s+number\s*[:#]?\s*([A-Z0-9][A-Z0-9\-.]*\d[A-Z0-9\-.]*)\b(?!\s*/)",
        re.IGNORECASE,
    ),
)

# Live Sports Card Store descriptions commonly end with a standalone team and
# catalogue-number line, for example "WESTERN BULLDOGS 159" while the title
# separately contains the serial "34/35". Requiring two or more all-caps team
# tokens and a short final number prevents generic prose and serial fractions
# from being promoted into identity. Conflicting candidate lines are rejected.
TEAM_LINE_CARD_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:[A-Z0-9][A-Z0-9'&.\-]*\s+){2,6}([A-Z]?\d{1,3}[A-Z]?)$"
)


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

            if not products:
                break

            for product in products:
                title = str(
                    product.get("title") or ""
                ).strip()

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

                variant = variants[0]

                if not variant.get("available", False):
                    continue

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

                identity = self._recover_identity_from_product(
                    parse_identity(title, sport),
                    product=product,
                )

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
                            "Sports Card Store Australia"
                        ),
                        condition="Raw / Store Listing",
                        identity=identity,
                    )
                )

                if len(listings) >= limit:
                    break

            if len(products) < page_size:
                break

            page += 1

        return listings[:limit]

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

        soup = BeautifulSoup(body_html, "html.parser")
        description = soup.get_text(" ", strip=True)
        for pattern in DESCRIPTION_CARD_NUMBER_PATTERNS:
            match = pattern.search(description)
            if not match:
                continue
            card_number = match.group(1).strip().upper()
            if card_number:
                return identity.model_copy(update={"card_number": card_number})

        candidates: set[str] = set()
        for raw_line in soup.get_text("\n", strip=True).splitlines():
            line = " ".join(raw_line.split())
            match = TEAM_LINE_CARD_NUMBER_RE.fullmatch(line)
            if match:
                candidates.add(match.group(1).upper())

        if len(candidates) == 1:
            return identity.model_copy(update={"card_number": candidates.pop()})

        return identity
