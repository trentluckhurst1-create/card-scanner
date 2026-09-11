from card_scanner.sources.the_hobby import SEALED_RE, TheHobbySource


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


def test_the_hobby_collects_in_stock_single_and_rejects_sealed_box():
    client = FakeClient({
        "products": [
            product("1", "Anthony Edwards 2021 Panini Prizm 37 PSA 10 NBA 75th Prizm"),
            product("2", "2025-26 Topps Chrome Black Basketball Hobby Box", price="950.00"),
        ]
    })
    rows = TheHobbySource(client=client).search("NBA", limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row.source == "thehobby"
    assert row.external_id == "1"
    assert row.price == 25.0
    assert row.identity.player
    assert row.identity.year
    assert row.identity.card_number == "37"
    assert "/collections/nba/products.json" in client.calls[0][0]


def test_the_hobby_recovers_alphanumeric_bare_card_number_before_grade():
    client = FakeClient({
        "products": [
            product("1", "Trae Young 2018 Panini Select 22A PSA 9 Silver"),
        ]
    })
    rows = TheHobbySource(client=client).search("NBA", limit=10)
    assert len(rows) == 1
    assert rows[0].identity.card_number == "22A"


def test_the_hobby_does_not_promote_unanchored_numbers_to_card_number():
    client = FakeClient({
        "products": [
            product("1", "Anthony Edwards 2021 Panini Prizm NBA 75th Prizm"),
        ]
    })
    rows = TheHobbySource(client=client).search("NBA", limit=10)
    assert len(rows) == 1
    assert rows[0].identity.card_number is None


def test_the_hobby_collection_handles_cover_current_card_scanner_sports():
    payload = {"products": []}
    client = FakeClient(payload)
    source = TheHobbySource(client=client)
    source.search("AFL")
    source.search("NBA")
    source.search("NFL")
    source.search("MLB")
    urls = [call[0] for call in client.calls]
    assert any("/collections/afl/products.json" in url for url in urls)
    assert any("/collections/nba/products.json" in url for url in urls)
    assert any("/collections/nfl/products.json" in url for url in urls)
    assert any("/collections/baseball-cards/products.json" in url for url in urls)


def test_sealed_filter_is_conservative_and_does_not_reject_card_titles():
    assert SEALED_RE.search("2026 Topps Chrome Baseball Value Box")
    assert SEALED_RE.search("2025 Panini Prizm Basketball Hobby Pack")
    assert not SEALED_RE.search("Anthony Edwards 2021 Panini Prizm 37 PSA 10")
    assert not SEALED_RE.search("James Hird 2005 Select Herald Sun S3 Authentic Signature 16/20")
