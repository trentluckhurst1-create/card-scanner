from __future__ import annotations
import base64
import time
import httpx
from card_scanner.currency import AudOnlyCurrencyProvider, CurrencyProvider
from card_scanner.config import settings
from card_scanner.identity import parse_identity
from card_scanner.models import Listing, MarketListing
from card_scanner.providers import ActiveMarketProvider
from card_scanner.risk import title_risk_flags
from .base import ListingSource


TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"


class EbaySource(ListingSource, ActiveMarketProvider):
    name = "ebay"

    def __init__(
        self,
        client: httpx.Client | None = None,
        currency_provider: CurrencyProvider | None = None,
    ):
        self.client_id = settings.ebay_client_id
        self.client_secret = settings.ebay_client_secret
        self.marketplace_id = settings.ebay_marketplace_id
        self.client = client or httpx.Client(timeout=30)
        self.currency_provider = currency_provider or AudOnlyCurrencyProvider()
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._query_cache: dict[tuple[str, str, str, int], list[MarketListing]] = {}

    def missing_credentials(self) -> list[str]:
        return [
            name
            for name, value in {
                "EBAY_CLIENT_ID": self.client_id,
                "EBAY_CLIENT_SECRET": self.client_secret,
            }.items()
            if not value
        ]

    def _token(self) -> str:
        now = time.time()

        if self._access_token and now < self._token_expires_at:
            return self._access_token

        missing = self.missing_credentials()
        if missing:
            raise RuntimeError(
                "Missing required eBay credentials: "
                + ", ".join(missing)
            )

        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        r = self.client.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
        )
        r.raise_for_status()
        payload = r.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 7200))
        self._token_expires_at = now + max(60, expires_in - 60)

        return self._access_token

    def search(self, sport: str, query: str, limit: int = 50) -> list[Listing]:
        out = []

        for item in self.search_market(sport, query, limit):
            listing = Listing(
                source=self.name,
                external_id=item.external_id,
                url=item.url,
                title=item.title,
                sport=sport.upper(),
                price=item.price,
                currency=item.currency,
                shipping=item.shipping or 0.0,
                image_url=item.image_url,
                seller=item.seller,
                condition=item.condition,
                identity=item.identity,
            )
            out.append(listing)

        return out

    def search_market(
        self,
        sport: str,
        query: str,
        limit: int = 50,
    ) -> list[MarketListing]:
        cache_key = (
            self.marketplace_id,
            sport.upper(),
            " ".join(query.split()).lower(),
            int(limit),
        )

        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        token = self._token()
        r = self.client.get(
            BROWSE_SEARCH_URL,
            params={
                "q": query,
                "limit": min(limit, 200),
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            },
        )
        r.raise_for_status()

        out: list[MarketListing] = []

        seen_ids: set[str] = set()

        for item in r.json().get("itemSummaries", []):
            external_id = item["itemId"]
            if external_id in seen_ids:
                continue
            seen_ids.add(external_id)
            price = item.get("price") or {}
            shipping_options = item.get("shippingOptions") or []
            shipping = None

            if shipping_options:
                shipping_cost = shipping_options[0].get("shippingCost") or {}

                try:
                    shipping = float(shipping_cost["value"])
                except Exception:
                    shipping = None

            title = item.get("title", "")
            currency = price.get("currency", "AUD")
            item_price = float(price.get("value", 0))
            reliable_shipping = shipping if shipping is not None else 0.0
            landed, fx_status = self.currency_provider.to_aud(
                item_price + reliable_shipping,
                currency,
            )
            listing = MarketListing(
                source=self.name,
                external_id=external_id,
                title=title,
                url=item.get("itemWebUrl", ""),
                price=item_price,
                currency=currency,
                shipping=shipping,
                seller=(item.get("seller") or {}).get("username"),
                condition=item.get("condition"),
                buying_option=", ".join(item.get("buyingOptions") or []),
                image_url=(item.get("image") or {}).get("imageUrl"),
                marketplace=self.marketplace_id,
                identity=parse_identity(title, sport),
                risk_flags=title_risk_flags(title),
                landed_price_aud=landed,
                fx_status=fx_status,
            )
            out.append(listing)

        self._query_cache[cache_key] = out

        return out
