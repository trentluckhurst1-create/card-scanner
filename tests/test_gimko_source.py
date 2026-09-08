from __future__ import annotations

import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from card_scanner.risk import title_risk_flags
from card_scanner.sources.gimko import GimkoSource


DETAIL_HTML = """
<html>
  <head>
    <title>Select Footy Stars 2018 - Adelaide Crows Full Team Base Set (w/ Adelaide AFLW) | Gimko</title>
  </head>
  <body>
    <a href="stores/boom-cards/">Boom Cards</a>
    <input type="hidden" name="auction_id" value="184230">
    <img id="main_image" src="thumbnail.php?pic=uplimg/BoomCards/img_A_184230_f1a059cc905747093e4ec3608535c844.jpg&w=500&sq=N&item=Y">
    <p class="desc">Price:</p>
    <div class="val b"><p>$2.00 AUD</p></div>
    <p class="desc">Shipping:</p>
    <div class="val"><p>$3.00 AUD - <a href="#">more information</a></p></div>
  </body>
</html>
"""


SINGLE_CARD_DETAIL_HTML = """
<html>
  <head>
    <title>2024 Select AFL Footy Stars NICK DAICOS Green 7/70 #10 | Gimko</title>
  </head>
  <body>
    <a href="/stores/boom-cards/">Boom Cards</a>
    <p class="desc">Price:</p>
    <div class="val b"><p>$20.00 AUD</p></div>
    <p class="desc">Shipping:</p>
    <div class="val"><p>$3.00 AUD</p></div>
  </body>
</html>
"""


SPORT_DETAIL_TITLES = {
    "NBA": "2009 Panini Prestige Chris Bosh Prestigious Pros #36/50 Raptors",
    "NFL": "2015 Panini Playbook Duke Johnson Rookie Dual Jersey 189/199 Cleveland Browns",
    "MLB": "2000 Bowman Chrome baseball Rocco Baldelli rookie card 91 - Tampa Bay Devil Rays",
}


EXPECTED_CATEGORY_PARAMS = {
    "AFL": ("afl-australian-rules-cards", "1921"),
    "NBA": ("basketball-cards", "1870"),
    "NFL": ("nfl-football-cards", "1922"),
    "MLB": ("baseball-cards", "1872"),
}


def category_html(*ids: str) -> str:
    links = "\n".join(
        f'<a href="select-footy-stars-2018-adelaide-crows-full-team-base-set-w-adelaide-aflw,name,{item_id},auction_id,auction_details">Item {item_id}</a>'
        for item_id in ids
    )

    return f"<html><body>{links}</body></html>"


def detail_html(title: str) -> str:
    return f"""
<html>
  <head>
    <title>{title} | Gimko</title>
  </head>
  <body>
    <a href="/stores/card-table/">Card Table</a>
    <p class="desc">Price:</p>
    <div class="val b"><p>$12.50 AUD</p></div>
    <p class="desc">Shipping:</p>
    <div class="val"><p>$4.00 AUD</p></div>
  </body>
</html>
"""


class GimkoSourceTests(unittest.TestCase):
    def source_for(self, handler):
        client = httpx.Client(
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        )
        return GimkoSource(client=client)

    def test_afl_buy_out_category_and_detail_parsing(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(str(request.url))
            if request.url.path.endswith("/categories.php"):
                self.assertIn("item_type=buy_out", str(request.url))
                return httpx.Response(200, text=category_html("184230"))
            return httpx.Response(200, text=DETAIL_HTML)

        listings = self.source_for(handler).search("AFL", limit=1)

        self.assertEqual(len(listings), 1)
        listing = listings[0]
        self.assertEqual(listing.source, "gimko")
        self.assertEqual(listing.external_id, "184230")
        self.assertEqual(
            listing.url,
            "https://www.gimko.com.au/select-footy-stars-2018-adelaide-crows-full-team-base-set-w-adelaide-aflw,name,184230,auction_id,auction_details",
        )
        self.assertEqual(
            listing.title,
            "Select Footy Stars 2018 - Adelaide Crows Full Team Base Set (w/ Adelaide AFLW)",
        )
        self.assertEqual(listing.price, 2.0)
        self.assertEqual(listing.shipping, 3.0)
        self.assertEqual(listing.seller, "Boom Cards")
        self.assertEqual(listing.currency, "AUD")
        self.assertEqual(listing.sport, "AFL")
        self.assertIsNotNone(listing.identity)
        self.assertIn("LOT_OR_BUNDLE", title_risk_flags(listing.title))
        self.assertTrue(listing.image_url.startswith("https://www.gimko.com.au/thumbnail.php"))

    def test_unsupported_sport_returns_empty(self):
        source = self.source_for(lambda request: httpx.Response(500))

        self.assertEqual(source.search("CRICKET", limit=5), [])

    def test_new_sports_use_verified_buy_out_category_params(self):
        for sport, title in SPORT_DETAIL_TITLES.items():
            with self.subTest(sport=sport):
                category, parent_id = EXPECTED_CATEGORY_PARAMS[sport]

                def handler(request: httpx.Request) -> httpx.Response:
                    if request.url.path.endswith("/categories.php"):
                        self.assertEqual(
                            request.url.params.get("item_type"),
                            "buy_out",
                        )
                        self.assertEqual(
                            request.url.params.get("category"),
                            category,
                        )
                        self.assertEqual(
                            request.url.params.get("parent_id"),
                            parent_id,
                        )
                        return httpx.Response(200, text=category_html("9001"))
                    return httpx.Response(200, text=detail_html(title))

                listings = self.source_for(handler).search(sport, limit=1)

                self.assertEqual(len(listings), 1)
                listing = listings[0]
                self.assertEqual(listing.sport, sport)
                self.assertEqual(listing.identity.sport, sport)
                self.assertEqual(listing.title, title)

    def test_query_filtering(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/categories.php"):
                return httpx.Response(200, text=category_html("184230"))
            return httpx.Response(200, text=DETAIL_HTML)

        self.assertEqual(self.source_for(handler).search("AFL", query="Collingwood", limit=1), [])
        self.assertEqual(len(self.source_for(handler).search("AFL", query="Adelaide", limit=1)), 1)

    def test_duplicate_item_ids_are_not_duplicated(self):
        detail_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal detail_calls
            if request.url.path.endswith("/categories.php"):
                return httpx.Response(200, text=category_html("184230", "184230"))
            detail_calls += 1
            return httpx.Response(200, text=DETAIL_HTML)

        listings = self.source_for(handler).search("AFL", limit=5)

        self.assertEqual(len(listings), 1)
        self.assertEqual(detail_calls, 1)

    def test_pagination_advances_to_start_50(self):
        starts = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/categories.php"):
                start = request.url.params.get("start", "0")
                starts.append(start)
                if start == "0":
                    return httpx.Response(200, text=category_html(*(str(i) for i in range(1000, 1050))))
                return httpx.Response(200, text=category_html("184230"))
            return httpx.Response(200, text=SINGLE_CARD_DETAIL_HTML)

        listings = self.source_for(handler).search("AFL", limit=51)

        self.assertEqual(len(listings), 51)
        self.assertIn("0", starts)
        self.assertIn("50", starts)

    def test_item_with_no_valid_positive_price_is_skipped(self):
        bad_detail = DETAIL_HTML.replace("$2.00 AUD", "$0.00 AUD")

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/categories.php"):
                return httpx.Response(200, text=category_html("184230"))
            return httpx.Response(200, text=bad_detail)

        self.assertEqual(self.source_for(handler).search("AFL", limit=1), [])

    def test_malformed_item_does_not_crash_scan(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/categories.php"):
                return httpx.Response(200, text=category_html("111", "184230"))
            if ",name,111," in str(request.url):
                return httpx.Response(200, text="<html><body>no price</body></html>")
            return httpx.Response(200, text=DETAIL_HTML)

        listings = self.source_for(handler).search("AFL", limit=5)

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].external_id, "184230")

    def test_shipping_parse_failure_skips_item_not_zero_shipping(self):
        bad_shipping = DETAIL_HTML.replace("$3.00 AUD", "ask seller")

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/categories.php"):
                return httpx.Response(200, text=category_html("184230"))
            return httpx.Response(200, text=bad_shipping)

        self.assertEqual(self.source_for(handler).search("AFL", limit=1), [])


if __name__ == "__main__":
    unittest.main()
