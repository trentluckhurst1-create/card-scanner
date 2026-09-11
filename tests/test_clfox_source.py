from card_scanner.sources.clfox import CLFoxSource


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


def product(product_id, title, *, available=True, price="25.00"):
    return {
        "id": product_id,
        "title": title,
        "handle": f"card-{product_id}",
        "variants": [{"available": available, "price": price}],
        "images": [{"src": f"https://img.test/{product_id}.jpg"}],
    }


def test_clfox_collects_active_nba_single():
    client = FakeClient({
        "products": [product("1", "2023-24 Panini Prizm Victor Wembanyama #136 Rookie")]
    })
    rows = CLFoxSource(client=client).search("NBA", query="Victor Wembanyama", limit=10)
    assert len(rows) == 1
    assert rows[0].source == "clfox"
    assert rows[0].price == 25.0
    assert rows[0].identity.player
    assert rows[0].identity.year


def test_clfox_reuses_shopify_page_across_targeted_queries():
    client = FakeClient({
        "products": [
            product("1", "2023-24 Panini Prizm Victor Wembanyama #136 Rookie"),
            product("2", "2023-24 Panini Prizm Stephen Curry #154"),
        ]
    })
    source = CLFoxSource(client=client)
    source.search("NBA", query="Victor Wembanyama", limit=10)
    source.search("NBA", query="Stephen Curry", limit=10)
    assert len(client.calls) == 1


def test_clfox_is_nba_only():
    client = FakeClient({"products": []})
    source = CLFoxSource(client=client)
    assert source.search("NFL") == []
    assert source.search("MLB") == []
    assert source.search("AFL") == []
    assert client.calls == []
