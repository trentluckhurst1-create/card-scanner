from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..identity import parse_identity
from ..models import Listing


BASE_URL = "https://www.gimko.com.au"

CATEGORY_BY_SPORT = {
    "AFL": (
        "afl-australian-rules-cards",
        "1921",
    ),
    "NBA": (
        "basketball-cards",
        "1870",
    ),
    "NFL": (
        "nfl-football-cards",
        "1922",
    ),
    "MLB": (
        "baseball-cards",
        "1872",
    ),
}

ITEM_LINK_RE = re.compile(
    r",name,(\d+),auction_id,auction_details$",
    re.IGNORECASE,
)

MONEY_RE = re.compile(
    r"\$([0-9]+(?:\.[0-9]{1,2})?)\s*AUD",
    re.IGNORECASE,
)


class GimkoSource:
    name = "gimko"
    source_name = "gimko"

    def __init__(
        self,
        client: httpx.Client | None = None,
    ) -> None:
        self._external_client = client is not None
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "CardScanner/1.0",
                "Accept": "text/html,application/xhtml+xml",
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

        if sport not in CATEGORY_BY_SPORT:
            return []

        limit = max(1, min(int(limit), 250))
        category, parent_id = CATEGORY_BY_SPORT[sport]

        listings: list[Listing] = []
        seen_ids: set[str] = set()
        start = 0

        while len(listings) < limit:
            response = self.client.get(
                f"{BASE_URL}/categories.php",
                params={
                    "item_type": "buy_out",
                    "page_url": "categories",
                    "category": category,
                    "parent_id": parent_id,
                    "limit": 50,
                    "start": start,
                },
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            item_urls: list[tuple[str, str]] = []

            for anchor in soup.find_all("a", href=True):
                href = str(anchor.get("href", "")).strip()
                href_path = href.split("?", 1)[0].rstrip("/")
                match = ITEM_LINK_RE.search(href_path)

                if not match:
                    continue

                external_id = match.group(1)

                if external_id in seen_ids:
                    continue

                seen_ids.add(external_id)
                item_urls.append(
                    (
                        external_id,
                        urljoin(BASE_URL, href_path),
                    )
                )

            if not item_urls:
                break

            for external_id, item_url in item_urls:
                try:
                    listing = self._fetch_listing(
                        external_id=external_id,
                        item_url=item_url,
                        sport=sport,
                    )
                except (httpx.HTTPError, ValueError):
                    continue

                if listing is None:
                    continue

                if query and query.casefold() not in listing.title.casefold():
                    continue

                listings.append(listing)

                if len(listings) >= limit:
                    break

            if len(item_urls) < 50:
                break

            start += 50

        return listings[:limit]

    def _fetch_listing(
        self,
        external_id: str,
        item_url: str,
        sport: str,
    ) -> Listing | None:
        response = self.client.get(item_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        title = self._extract_title(soup)

        if not title:
            return None

        price = self._extract_label_money(
            soup,
            "Price:",
        )

        if price is None or price <= 0:
            return None

        shipping = self._extract_label_money(
            soup,
            "Shipping:",
        )

        if shipping is None:
            shipping = 0.0
        elif shipping <= 0:
            shipping = 0.0

        seller = self._extract_seller(soup)
        image_url = self._extract_image(soup)

        return Listing(
            source=self.source_name,
            external_id=external_id,
            url=item_url,
            title=title,
            sport=sport,
            price=price,
            currency="AUD",
            shipping=shipping,
            image_url=image_url,
            seller=seller,
            condition="Marketplace Listing",
            identity=parse_identity(title, sport),
        )

    @staticmethod
    def _extract_title(
        soup: BeautifulSoup,
    ) -> str | None:
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            title = re.sub(
                r"\s*\|\s*Gimko\s*$",
                "",
                title,
                flags=re.IGNORECASE,
            ).strip()

            if title:
                return title

        image = soup.find("img", id="main_image")

        if image:
            alt = str(image.get("alt", "")).strip()

            if alt:
                return alt

        return None

    @staticmethod
    def _extract_label_money(
        soup: BeautifulSoup,
        label: str,
    ) -> float | None:
        label_node = None

        for node in soup.find_all("p", class_="desc"):
            if node.get_text(" ", strip=True).casefold() == label.casefold():
                label_node = node
                break

        if label_node is None:
            return None

        sibling = label_node.find_next_sibling()

        if sibling is None:
            raise ValueError(f"Gimko money label found without value: {label}")

        match = MONEY_RE.search(
            sibling.get_text(" ", strip=True)
        )

        if not match:
            raise ValueError(f"Gimko money label could not be parsed: {label}")

        return float(match.group(1))

    @staticmethod
    def _extract_seller(
        soup: BeautifulSoup,
    ) -> str | None:
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href", "")).strip()

            match = re.search(
                r"(?:^|/)stores/([^/]+)/?$",
                href,
                re.IGNORECASE,
            )

            if not match:
                continue

            slug = match.group(1).strip()

            if not slug:
                continue

            return slug.replace("-", " ").title()

        return None

    @staticmethod
    def _extract_image(
        soup: BeautifulSoup,
    ) -> str | None:
        image = soup.find("img", id="main_image")

        if image is None:
            return None

        src = str(image.get("src", "")).strip()

        if not src:
            return None

        return urljoin(BASE_URL, src)
