from __future__ import annotations

import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from card_scanner.sources.ebay import BROWSE_SEARCH_URL, TOKEN_URL, EbaySource


class EbaySourceTests(unittest.TestCase):
    def test_token_and_query_are_cached(self):
        calls = {"token": 0, "search": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == TOKEN_URL:
                calls["token"] += 1
                return httpx.Response(
                    200,
                    json={"access_token": "token", "expires_in": 7200},
                )

            if str(request.url).startswith(BROWSE_SEARCH_URL):
                calls["search"] += 1
                return httpx.Response(
                    200,
                    json={
                        "itemSummaries": [
                            {
                                "itemId": "v1|123",
                                "title": "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
                                "itemWebUrl": "https://www.ebay.com.au/itm/123",
                                "price": {"value": "100.00", "currency": "AUD"},
                                "shippingOptions": [
                                    {"shippingCost": {"value": "10.00", "currency": "AUD"}}
                                ],
                                "seller": {"username": "seller"},
                                "condition": "Ungraded",
                                "buyingOptions": ["FIXED_PRICE"],
                                "image": {"imageUrl": "https://example.invalid/card.jpg"},
                            }
                        ]
                    },
                )

            return httpx.Response(404, json={"url": str(request.url)})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        source = EbaySource(client=client)
        source.client_id = "id"
        source.client_secret = "secret"

        first = source.search_market("MLB", "kyson witherspoon", 5)
        second = source.search_market("MLB", "kyson witherspoon", 5)

        self.assertEqual(len(first), 1)
        self.assertEqual(second[0].landed_price_aud, 110.0)
        self.assertEqual(second[0].fx_status, "CONVERTED")
        self.assertEqual(calls, {"token": 1, "search": 1})

    def test_missing_credentials_fail_clearly(self):
        source = EbaySource(client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))))
        source.client_id = ""
        source.client_secret = ""

        with self.assertRaisesRegex(RuntimeError, "EBAY_CLIENT_ID.*EBAY_CLIENT_SECRET"):
            source.search_market("MLB", "anything", 5)

    def test_empty_search(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == TOKEN_URL:
                return httpx.Response(200, json={"access_token": "token", "expires_in": 7200})
            return httpx.Response(200, json={"itemSummaries": []})

        source = EbaySource(client=httpx.Client(transport=httpx.MockTransport(handler)))
        source.client_id = "id"
        source.client_secret = "secret"

        self.assertEqual(source.search_market("MLB", "nothing", 5), [])

    def test_duplicate_listing_dedupes(self):
        item = {
            "itemId": "v1|123",
            "title": "2025 Bowman Draft KYSON WITHERSPOON Chrome Prospect 1st Auto Gold Wave 7/50",
            "itemWebUrl": "https://www.ebay.com.au/itm/123",
            "price": {"value": "100.00", "currency": "AUD"},
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == TOKEN_URL:
                return httpx.Response(200, json={"access_token": "token", "expires_in": 7200})
            return httpx.Response(200, json={"itemSummaries": [item, item]})

        source = EbaySource(client=httpx.Client(transport=httpx.MockTransport(handler)))
        source.client_id = "id"
        source.client_secret = "secret"

        self.assertEqual(len(source.search_market("MLB", "kyson", 5)), 1)

    def test_auth_failure_raises_http_status(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == TOKEN_URL:
                return httpx.Response(401, json={"error": "invalid_client"}, request=request)
            return httpx.Response(200, json={})

        source = EbaySource(client=httpx.Client(transport=httpx.MockTransport(handler)))
        source.client_id = "id"
        source.client_secret = "bad"

        with self.assertRaises(httpx.HTTPStatusError):
            source.search_market("MLB", "kyson", 5)

    def test_rate_limit_raises_http_status(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == TOKEN_URL:
                return httpx.Response(200, json={"access_token": "token", "expires_in": 7200})
            return httpx.Response(429, json={"error": "rate_limit"}, request=request)

        source = EbaySource(client=httpx.Client(transport=httpx.MockTransport(handler)))
        source.client_id = "id"
        source.client_secret = "secret"

        with self.assertRaises(httpx.HTTPStatusError):
            source.search_market("MLB", "kyson", 5)


if __name__ == "__main__":
    unittest.main()
