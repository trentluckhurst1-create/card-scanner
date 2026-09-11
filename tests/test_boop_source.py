from card_scanner.sources.boop import BoopSource


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


def product(product_id, title, *, available=True, price="35.00", body_html=""):
    return {
        "id": product_id,
        "title": title,
        "handle": f"card-{product_id}",
        "variants": [{"available": available, "price": price}],
        "images": [{"src": f"https://img.test/{product_id}.jpg"}],
        "body_html": body_html,
    }


def test_boop_collects_in_stock_nba_single():
    client = FakeClient({
        "products": [
            product("1", "Darius Garland 2019-20 Panini Origins Black RC 1/1"),
        ]
    })
    rows = BoopSource(client=client).search("NBA", limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row.source == "boop"
    assert row.external_id == "1"
    assert row.price == 35.0
    assert row.identity.player
    assert row.identity.year
    assert "/collections/nba-singles/products.json" in client.calls[0][0]


def test_boop_recovers_explicit_card_number_from_description():
    client = FakeClient({
        "products": [
            product(
                "1",
                "Darius Garland 2019-20 Panini Origins Black RC 1/1",
                body_html="<p>2019-20 Panini Origins rookie. Card No. 35.</p>",
            ),
        ]
    })
    row = BoopSource(client=client).search("NBA", limit=10)[0]
    assert row.identity.card_number == "35"


def test_boop_description_recovery_rejects_unlabelled_and_serial_numbers():
    unlabelled = product(
        "1",
        "Darius Garland 2019-20 Panini Origins Black RC 1/1",
        body_html="<p>Origins 35 anniversary release.</p>",
    )
    serial = product(
        "2",
        "Darius Garland 2019-20 Panini Origins Black RC 1/1",
        body_html="<p>Card #10/10 serial numbered.</p>",
    )
    rows = BoopSource(client=FakeClient({"products": [unlabelled, serial]})).search("NBA", limit=10)
    assert all(row.identity.card_number is None for row in rows)


def test_boop_routes_nfl_and_afl_collections():
    client = FakeClient({"products": []})
    source = BoopSource(client=client)
    source.search("NFL")
    source.search("AFL")
    assert "/collections/nfl-singles/products.json" in client.calls[0][0]
    assert "/collections/afl-singles/products.json" in client.calls[1][0]


def test_boop_skips_unavailable_product():
    client = FakeClient({
        "products": [
            product("1", "Aaron Glenn 2024 Panini Prizm Purple Power Sensational Auto 25/49", available=False),
        ]
    })
    assert BoopSource(client=client).search("NFL", limit=10) == []


def test_boop_does_not_claim_mlb_without_a_proven_collection():
    client = FakeClient({"products": []})
    source = BoopSource(client=client)
    assert source.search("MLB") == []
    assert client.calls == []
