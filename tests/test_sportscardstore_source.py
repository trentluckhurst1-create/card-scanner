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

        if isinstance(self.payload, list):
            page = int((params or {}).get("page", 1))
            index = page - 1

            if 0 <= index < len(self.payload):
                payload = self.payload[index]
            else:
                payload = {"products": []}

            return FakeResponse(payload)

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
            {"limit": 250, "page": 1},
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

def make_product(
    product_id: int,
    title: str,
    *,
    available: bool = True,
    price: str = "10.00",
) -> dict:
    return {
        "id": product_id,
        "title": title,
        "handle": f"card-{product_id}",
        "variants": [
            {
                "available": available,
                "price": price,
            }
        ],
        "images": [],
    }


def test_sportscardstore_source_paginates_until_query_match() -> None:
    first_page = [
        make_product(
            product_id,
            f"Other Player Card {product_id}",
        )
        for product_id in range(1, 251)
    ]

    second_page = [
        make_product(
            251,
            "2019-20 PANINI DONRUSS OPTIC Ja Morant Rated Rookie RC",
        )
    ]

    client = FakeClient(
        [
            {"products": first_page},
            {"products": second_page},
        ]
    )
    source = SportsCardStoreSource(client=client)

    rows = source.search(
        "NBA",
        query="Ja Morant",
        limit=5,
    )

    assert len(rows) == 1
    assert rows[0].identity.player == "Ja Morant"

    assert len(client.calls) == 2
    assert client.calls[0][1] == {
        "limit": 250,
        "page": 1,
    }
    assert client.calls[1][1] == {
        "limit": 250,
        "page": 2,
    }


def test_sportscardstore_source_stops_when_limit_reached() -> None:
    first_page = [
        make_product(
            product_id,
            f"NBA Player Card {product_id}",
        )
        for product_id in range(1, 251)
    ]

    client = FakeClient(
        [
            {"products": first_page},
            {
                "products": [
                    make_product(
                        251,
                        "Should Never Be Requested",
                    )
                ]
            },
        ]
    )
    source = SportsCardStoreSource(client=client)

    rows = source.search(
        "NBA",
        limit=2,
    )

    assert len(rows) == 2
    assert len(client.calls) == 1


def test_sportscardstore_source_skips_unavailable_across_pages() -> None:
    first_page = [
        make_product(
            product_id,
            f"Target Player Card {product_id}",
            available=False,
        )
        for product_id in range(1, 251)
    ]

    second_page = [
        make_product(
            251,
            "Target Player Available Card",
        )
    ]

    client = FakeClient(
        [
            {"products": first_page},
            {"products": second_page},
        ]
    )
    source = SportsCardStoreSource(client=client)

    rows = source.search(
        "NBA",
        query="Target Player",
        limit=1,
    )

    assert len(rows) == 1
    assert rows[0].external_id == "251"
    assert len(client.calls) == 2


def test_sportscardstore_source_deduplicates_products_across_pages() -> None:
    first_page = [
        make_product(
            1,
            "Target Player First Card",
        )
    ]

    first_page.extend(
        make_product(
            product_id,
            f"Other Player Card {product_id}",
        )
        for product_id in range(2, 251)
    )

    second_page = [
        make_product(
            1,
            "Target Player First Card",
        ),
        make_product(
            251,
            "Target Player Second Card",
        ),
    ]

    client = FakeClient(
        [
            {"products": first_page},
            {"products": second_page},
        ]
    )
    source = SportsCardStoreSource(client=client)

    rows = source.search(
        "NBA",
        query="Target Player",
        limit=2,
    )

    assert len(rows) == 2
    assert [row.external_id for row in rows] == [
        "1",
        "251",
    ]
    assert len(client.calls) == 2


def test_sportscardstore_source_stops_on_short_final_page() -> None:
    client = FakeClient(
        [
            {
                "products": [
                    make_product(
                        1,
                        "Completely Different Player",
                    )
                ]
            }
        ]
    )
    source = SportsCardStoreSource(client=client)

    rows = source.search(
        "NBA",
        query="Target Player",
        limit=5,
    )

    assert rows == []
    assert len(client.calls) == 1
