from __future__ import annotations

import re
from typing import Final

import httpx

from ..identity import parse_identity
from ..models import Listing

BASE_URL: Final[str] = "https://www.localcardshop.com.au"
SPORT_TOKEN = {"AFL": "afl", "NBA": "nba", "NFL": "nfl", "MLB": "mlb"}
PRICE_RE = re.compile(r"(?:A\$|\$)\s*([0-9]+(?:\.[0-9]{1,2})?)")


class LocalCardShopSource:
    """Public singles-page discovery. Conservative: only rows with parsed player/year are emitted."""

    name = "localcardshop"
    source_name = "localcardshop"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._external_client = client is not None
        self.client = client or httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})

    def close(self) -> None:
        if not self._external_client:
            self.client.close()

    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        sport = sport.upper().strip()
        token = SPORT_TOKEN.get(sport)
        if token is None:
            return []
        response = self.client.get(f"{BASE_URL}/singles")
        response.raise_for_status()
        html = response.text
        # Wix pages expose product names/prices/URLs in rendered payloads. Extract
        # conservatively; if the public markup changes, fail closed with no rows.
        href_title = re.findall(r'href=["\']([^"\']+)["\'][^>]*>([^<]{8,220})<', html, flags=re.I)
        query_norm = query.strip().casefold()
        output: list[Listing] = []
        seen: set[str] = set()
        for href, raw_title in href_title:
            title = re.sub(r"\s+", " ", re.sub(r"&[^;]+;", " ", raw_title)).strip()
            low = title.casefold()
            if token not in low and sport.casefold() not in low:
                continue
            if query_norm and query_norm not in low:
                continue
            identity = parse_identity(title, sport)
            if not identity.player or not identity.year:
                continue
            pos = html.find(raw_title)
            window = html[pos:pos + 1200] if pos >= 0 else ""
            match = PRICE_RE.search(window)
            if not match:
                continue
            price = float(match.group(1))
            url = href if href.startswith("http") else f"{BASE_URL}{href if href.startswith('/') else '/' + href}"
            if url in seen:
                continue
            seen.add(url)
            output.append(Listing(source=self.source_name, external_id=url, url=url, title=title, sport=sport, price=price, currency="AUD", shipping=0.0, seller="Local Card Shop", condition="Store Listing", identity=identity))
            if len(output) >= max(1, int(limit)):
                break
        return output
