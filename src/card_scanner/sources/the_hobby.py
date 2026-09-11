from __future__ import annotations

import re
from typing import Final

import httpx

from ..identity import parse_identity
from ..models import CardIdentity, Listing


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

# The Hobby frequently writes catalogue numbers as bare tokens. The simplest
# form is immediately before the grade ("Prizm 37 PSA 10"), but production
# titles also use "Select 257 White Disco 9/75 PSA 10" and
# "Donruss 201 Press Proof Purple 141/199 PSA 10". The generic parser must not
# guess arbitrary numbers, so this recovery remains source-specific and only
# operates on titles with an explicit grading-company/grade suffix.
BARE_CARD_BEFORE_GRADE_RE = re.compile(
    r"(?<![A-Za-z0-9#/])([A-Z]?\d{1,3}[A-Z]?)(?=\s+(?:PSA|BGS|SGC|CGC)\s*\d+(?:\.\d+)?\b)",
    re.IGNORECASE,
)
GRADE_MARKER_RE = re.compile(r"\b(?:PSA|BGS|SGC|CGC)\s*\d+(?:\.\d+)?\b", re.IGNORECASE)
SEASON_RE = re.compile(r"\b(?:19|20)\d{2}(?:-(?:\d{2}|(?:19|20)\d{2}))?\b")
SERIAL_RE = re.compile(r"(?<![A-Za-z0-9])\d{1,4}\s*/\s*\d{1,5}(?![A-Za-z0-9])")
BARE_CARD_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9#/])([A-Z]?\d{1,3}[A-Z]?)(?![A-Za-z0-9/])", re.IGNORECASE)


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


def _recover_bare_card_number(title: str, identity: CardIdentity) -> CardIdentity:
    if identity.card_number:
        return identity

    direct = BARE_CARD_BEFORE_GRADE_RE.search(title)
    if direct:
        return identity.model_copy(update={"card_number": direct.group(1).upper()})

    grade = GRADE_MARKER_RE.search(title)
    if not grade:
        return identity

    # Only inspect the pre-grade portion. Remove seasons and serial fractions,
    # then take the final remaining short number token. In The Hobby's graded
    # title convention that token is the catalogue number while later numeric
    # content is the serial copy, which was removed above. This deliberately
    # does not run on raw/ungraded titles.
    prefix = title[: grade.start()]
    prefix = SEASON_RE.sub(" ", prefix)
    prefix = SERIAL_RE.sub(" ", prefix)
    candidates = [match.group(1).upper() for match in BARE_CARD_TOKEN_RE.finditer(prefix)]
    if not candidates:
        return identity

    return identity.model_copy(update={"card_number": candidates[-1]})


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

                identity = _recover_bare_card_number(
                    title,
                    parse_identity(title, sport),
                )
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
