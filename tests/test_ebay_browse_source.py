from card_scanner.sources.ebay_browse import EbayBrowseSource


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): return None
    def json(self): return self.payload


class FakeClient:
    def __init__(self): self.posts = []; self.gets = []
    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse({"access_token": "TOKEN"})
    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return FakeResponse({"itemSummaries": [{
            "itemId": "v1|123|0",
            "title": "2024 Panini Prizm Player Silver /10 #7",
            "itemWebUrl": "https://www.ebay.com.au/itm/123",
            "price": {"value": "25.00", "currency": "AUD"},
            "shippingOptions": [{"shippingCost": {"value": "5.00", "currency": "AUD"}}],
            "image": {"imageUrl": "https://i.ebayimg.com/example.jpg"},
            "seller": {"username": "seller"},
            "condition": "Ungraded",
        }]})


def test_unconfigured_source_is_secret_safe_and_returns_no_rows():
    source = EbayBrowseSource(client_id="", client_secret="", client=FakeClient())
    assert source.configured is False
    assert source.search("NBA", "Player", 10) == []


def test_empty_query_does_not_issue_broad_ebay_search():
    client = FakeClient()
    source = EbayBrowseSource(client_id="id", client_secret="secret", client=client)
    assert source.search("NBA", "", 10) == []
    assert client.gets == []


def test_targeted_search_uses_application_token_and_marketplace():
    client = FakeClient()
    source = EbayBrowseSource(client_id="id", client_secret="secret", client=client)
    rows = source.search("NBA", "2024 Panini Prizm Player Silver /10 #7", 10)
    assert len(rows) == 1
    row = rows[0]
    assert row.source == "ebay"
    assert row.external_id == "v1|123|0"
    assert row.price == 25.0
    assert row.shipping == 5.0
    assert row.currency == "AUD"
    assert row.image_url
    assert len(client.posts) == 1
    assert client.gets[0][1]["headers"]["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_AU"
    assert client.gets[0][1]["params"]["q"].endswith("/10 #7")
