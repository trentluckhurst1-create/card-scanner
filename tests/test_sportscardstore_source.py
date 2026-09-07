from card_scanner.sources.sportscardstore import SportsCardStoreSource


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

    def close(self):
        return None


def test_sportscardstore_source_parses_available_listing() -> None:
    payload = {
        "products": [
            {
                "id": 12345,
                "title": "2019-20 PANINI DONRUSS OPTIC Ja Morant Rated Rookie RC NBA Basketball Card PSA 10",
                "handle": "ja-morant-rated-rookie-psa-10",
                "variants": [
                    {
                        "available": True,
                        "price": "229.00",
                    }
                ],
                "images": [
                    {
                        "src": "https://example.com/card.jpg",
                    }
                ],
            }
        ]
    }

    client = FakeClient(payload)
    source = SportsCardStoreSource(client=client)

    rows = source.search("NBA", limit=5)

    assert len(rows) == 1

    row = rows[0]

    assert row.source == "sportscardstore"
    assert row.external_id == "12345"
    assert row.price == 229.0
    assert row.currency == "AUD"
    assert row.shipping == 0.0
    assert row.seller == "Sports Card Store Australia"
    assert row.identity.player == "Ja Morant"
    assert row.identity.grader == "PSA"
    assert row.identity.grade == 10.0
    assert row.url.endswith("/products/ja-morant-rated-rookie-psa-10")

    assert client.calls == [
        (
            "https://sportscardstore.com.au/collections/nba-singles/products.json",
            {"limit": 5},
        )
    ]


def test_sportscardstore_source_skips_unavailable_and_bad_prices() -> None:
    payload = {
        "products": [
            {
                "id": 1,
                "title": "Unavailable Card",
                "handle": "unavailable-card",
                "variants": [
                    {
                        "available": False,
                        "price": "25.00",
                    }
                ],
            },
            {
                "id": 2,
                "title": "Zero Price Card",
                "handle": "zero-price-card",
                "variants": [
                    {
                        "available": True,
                        "price": "0.00",
                    }
                ],
            },
        ]
    }

    client = FakeClient(payload)
    source = SportsCardStoreSource(client=client)

    rows = source.search("AFL", limit=10)

    assert rows == []


def test_sportscardstore_source_rejects_unsupported_sport_without_call() -> None:
    client = FakeClient({"products": []})
    source = SportsCardStoreSource(client=client)

    rows = source.search("NFL", limit=5)

    assert rows == []
    assert client.calls == []
