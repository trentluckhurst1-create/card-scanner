from card_scanner.sources.eastside import EastsideSource


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return FakeResponse(self.payload)


def product(product_id, title, *, available=True, price="35.00"):
    return {
        "id": product_id,
        "title": title,
        "handle": f"card-{product_id}",
        "variants": [{"available": available, "price": price}],
        "images": [{"src": f"https://img.test/{product_id}.jpg"}],
    }


def test_eastside_collects_in_stock_nba_single():
    client = FakeClient({
        "products": [
            product("1", "1995-96 Topps Kevin Garnett 237 Rookie"),
        ]
    })
    rows = EastsideSource(client=client).search("NBA", limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row.source == "eastside"
    assert row.external_id == "1"
    assert row.price == 35.0
    assert row.identity.player
    assert row.identity.year
    assert "/collections/raw/products.json" in client.calls[0][0]


def test_eastside_skips_unavailable_product():
    client = FakeClient({
        "products": [
            product("1", "1996-97 Fleer Ultra Michael Jordan Decade of Excellence U4", available=False),
        ]
    })
    assert EastsideSource(client=client).search("NBA", limit=10) == []


def test_eastside_is_nba_only_during_source_proving():
    client = FakeClient({"products": []})
    source = EastsideSource(client=client)
    assert source.search("NFL") == []
    assert source.search("MLB") == []
    assert source.search("AFL") == []
    assert client.calls == []


def test_eastside_reuses_shopify_page_across_targeted_queries():
    client = FakeClient({
        "products": [
            product("1", "1995-96 Topps Kevin Garnett 237 Rookie"),
            product("2", "1995-96 Topps Michael Jordan 1"),
        ]
    })
    source = EastsideSource(client=client)
    source.search("NBA", query="Kevin Garnett", limit=10)
    source.search("NBA", query="Michael Jordan", limit=10)
    assert len(client.calls) == 1
