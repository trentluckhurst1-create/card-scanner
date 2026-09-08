from card_scanner.sources.urban_empire import UrbanEmpireSource


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        page = int((params or {}).get("page", 1))
        payload = self.pages.get(
            page,
            {"products": []},
        )
        return FakeResponse(payload)

    def close(self):
        return None


def make_product(
    product_id: int,
    title: str,
    *,
    price: str = "10.00",
    available: bool = True,
    second_variant_available: bool = False,
) -> dict:
    variants = [
        {
            "available": available,
            "price": price,
        }
    ]

    if second_variant_available:
        variants = [
            {
                "available": False,
                "price": "1.00",
            },
            {
                "available": True,
                "price": price,
            },
        ]

    return {
        "id": product_id,
        "title": title,
        "handle": f"card-{product_id}",
        "variants": variants,
        "images": [
            {
                "src": f"https://example.com/{product_id}.jpg",
            }
        ],
    }


def test_urban_empire_parses_available_nba_listing() -> None:
    client = FakeClient(
        {
            1: {
                "products": [
                    make_product(
                        1,
                        (
                            "2019-20 Panini Prizm "
                            "Ja Morant Rookie RC PSA 10"
                        ),
                        price="229.00",
                    )
                ]
            }
        }
    )

    source = UrbanEmpireSource(client=client)
    rows = source.search("NBA", limit=5)

    assert len(rows) == 1

    row = rows[0]

    assert row.source == "urbanempire"
    assert row.external_id == "1"
    assert row.price == 229.0
    assert row.currency == "AUD"
    assert row.shipping == 0.0
    assert row.seller == "Urban Empire Collectables"
    assert row.identity.player == "Ja Morant"
    assert row.identity.grader == "PSA"
    assert row.identity.grade == 10.0


def test_urban_empire_supports_nfl() -> None:
    client = FakeClient(
        {
            1: {
                "products": [
                    make_product(
                        2,
                        (
                            "2024 Panini Gold Standard "
                            "Drake Maye Rookie #103 /65"
                        ),
                    )
                ]
            }
        }
    )

    source = UrbanEmpireSource(client=client)
    rows = source.search("NFL", limit=5)

    assert len(rows) == 1
    assert rows[0].sport == "NFL"
    assert rows[0].identity.player == "Drake Maye"
    assert rows[0].identity.serial_total == 65


def test_urban_empire_rejects_unsupported_sports_without_call() -> None:
    client = FakeClient({})
    source = UrbanEmpireSource(client=client)

    assert source.search("MLB", limit=5) == []
    assert source.search("AFL", limit=5) == []
    assert client.calls == []


def test_urban_empire_uses_available_variant() -> None:
    client = FakeClient(
        {
            1: {
                "products": [
                    make_product(
                        3,
                        "2024 Panini Select Victor Wembanyama Rookie RC",
                        price="75.00",
                        second_variant_available=True,
                    )
                ]
            }
        }
    )

    source = UrbanEmpireSource(client=client)
    rows = source.search("NBA", limit=5)

    assert len(rows) == 1
    assert rows[0].price == 75.0


def test_urban_empire_skips_unavailable_and_bad_price() -> None:
    client = FakeClient(
        {
            1: {
                "products": [
                    make_product(
                        4,
                        "Unavailable Card",
                        available=False,
                    ),
                    make_product(
                        5,
                        "Bad Price Card",
                        price="0.00",
                    ),
                ]
            }
        }
    )

    source = UrbanEmpireSource(client=client)

    assert source.search("NBA", limit=10) == []


def test_urban_empire_paginates_for_query_match() -> None:
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
            "2024 Panini Prizm Luka Doncic Silver",
        )
    ]

    client = FakeClient(
        {
            1: {"products": first_page},
            2: {"products": second_page},
        }
    )

    source = UrbanEmpireSource(client=client)

    rows = source.search(
        "NBA",
        query="Luka Doncic",
        limit=5,
    )

    assert len(rows) == 1
    assert rows[0].identity.player == "Luka Doncic"
    assert len(client.calls) == 2


def test_urban_empire_stops_when_limit_reached() -> None:
    products = [
        make_product(
            product_id,
            f"NBA Card {product_id}",
        )
        for product_id in range(1, 251)
    ]

    client = FakeClient(
        {
            1: {"products": products},
            2: {
                "products": [
                    make_product(
                        251,
                        "Should Not Be Requested",
                    )
                ]
            },
        }
    )

    source = UrbanEmpireSource(client=client)

    rows = source.search("NBA", limit=2)

    assert len(rows) == 2
    assert len(client.calls) == 1


def test_urban_empire_deduplicates_across_pages() -> None:
    first_page = [
        make_product(
            1,
            "Target Player Card One",
        )
    ]

    first_page.extend(
        make_product(
            product_id,
            f"Other Card {product_id}",
        )
        for product_id in range(2, 251)
    )

    second_page = [
        make_product(
            1,
            "Target Player Card One",
        ),
        make_product(
            251,
            "Target Player Card Two",
        ),
    ]

    client = FakeClient(
        {
            1: {"products": first_page},
            2: {"products": second_page},
        }
    )

    source = UrbanEmpireSource(client=client)

    rows = source.search(
        "NBA",
        query="Target Player",
        limit=2,
    )

    assert [row.external_id for row in rows] == [
        "1",
        "251",
    ]
    assert len(client.calls) == 2


def test_urban_empire_stops_on_short_final_page() -> None:
    client = FakeClient(
        {
            1: {
                "products": [
                    make_product(
                        1,
                        "Completely Different Player",
                    )
                ]
            }
        }
    )

    source = UrbanEmpireSource(client=client)

    rows = source.search(
        "NBA",
        query="Target Player",
        limit=5,
    )

    assert rows == []
    assert len(client.calls) == 1
