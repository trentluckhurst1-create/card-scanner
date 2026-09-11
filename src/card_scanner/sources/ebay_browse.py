from __future__ import annotations

import base64
import os
from typing import Any

import httpx

from card_scanner.identity import parse_identity
from card_scanner.models import Listing
from .base import ListingSource


TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
DEFAULT_MARKETPLACE = "EBAY_AU"
DEFAULT_SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayBrowseSource(ListingSource):
    """Active eBay inventory via the official Browse API.

    Credentials are read only from environment variables and are never written
    to published feeds. Browse results are active asks, not sold evidence.
    """

    name = "ebay"

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        marketplace_id: str = DEFAULT_MARKETPLACE,
        client: httpx.Client | None = None,
    ):
        self.client_id = client_id or os.getenv("EBAY_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("EBAY_CLIENT_SECRET", "")
        self.marketplace_id = marketplace_id
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)
        self._access_token: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        if not self.configured:
            raise RuntimeError("eBay Browse API credentials are not configured")

        basic = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("ascii")
        response = self.client.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": DEFAULT_SCOPE},
        )
        response.raise_for_status()
        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("eBay OAuth response missing access_token")
        self._access_token = token
        return token

    @staticmethod
    def _amount(value: Any) -> float:
        if isinstance(value, dict):
            value = value.get("value")
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def item_to_listing(self, item: dict, sport: str) -> Listing:
        title = " ".join(str(item.get("title") or "").split())
        item_id = str(item.get("itemId") or "").strip()
        url = str(item.get("itemWebUrl") or "").strip()
        price_obj = item.get("price") or {}
        price = self._amount(price_obj)
        currency = str(price_obj.get("currency") or "AUD").upper()
        if not title or not item_id or not url or price <= 0:
            raise ValueError("eBay item missing required active-listing fields")

        shipping = 0.0
        shipping_options = item.get("shippingOptions") or []
        if shipping_options:
            shipping = self._amount((shipping_options[0] or {}).get("shippingCost"))

        image = item.get("image") or {}
        seller = item.get("seller") or {}
        condition = str(item.get("condition") or "").strip() or None

        return Listing(
            source=self.name,
            external_id=item_id,
            url=url,
            title=title,
            sport=sport.upper(),
            price=price,
            currency=currency,
            shipping=shipping,
            image_url=str(image.get("imageUrl") or "").strip() or None,
            seller=str(seller.get("username") or "").strip() or None,
            condition=condition,
            identity=parse_identity(title, sport.upper()),
        )

    def search(self, sport: str, query: str = "", limit: int = 50) -> list[Listing]:
        if not self.configured:
            return []

        limit = max(1, min(int(limit), 200))
        q = " ".join(str(query or "").split())
        if not q:
            # Broad eBay searches are intentionally avoided. Native eBay is
            # used for targeted card discovery against known identities.
            return []

        response = self.client.get(
            SEARCH_URL,
            headers={
                "Authorization": f"Bearer {self._token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
                "Accept": "application/json",
            },
            params={"q": q, "limit": limit},
        )
        response.raise_for_status()
        payload = response.json()
        output: list[Listing] = []
        for item in payload.get("itemSummaries") or []:
            try:
                output.append(self.item_to_listing(item, sport))
            except ValueError:
                continue
        return output
