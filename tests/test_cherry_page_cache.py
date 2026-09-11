from __future__ import annotations

from card_scanner.sources.cherry import CherrySource, SHOPIFY_PAGE_SIZE


class _Response:
    def __init__(self, products):
        self._products = products

    def raise_for_status(self):
        return None

    def json(self):
        return {"products": self._products}


class _Client:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params):
        self.calls.append((url, dict(params)))
        page = int(params["page"])
        return _Response(self.pages.get(page, []))


def _product(product_id: int, title: str):
    return {
        "id": product_id,
        "handle": f"card-{product_id}",
        "title": title,
        "variants": [{"price": "10.00", "available": True}],
        "images": [],
    }


def test_cherry_targeted_search_uses_shopify_250_page_size_and_respects_limit():
    source = CherrySource()
    products = [_product(i, f"2025 Topps Chrome Test Player Silver #{i}") for i in range(1, 251)]
    source.client.close()
    source.client = _Client({1: products, 2: []})

    rows = source.search("NFL", query="Test Player", limit=5)

    assert len(rows) == 5
    assert source.client.calls == [
        (
            "https://www.cherrycollectables.com.au/collections/nfl-singles/products.json",
            {"limit": SHOPIFY_PAGE_SIZE, "page": 1},
        )
    ]
    assert SHOPIFY_PAGE_SIZE == 250


def test_cherry_repeated_player_search_reuses_cached_collection_pages():
    source = CherrySource()
    page1 = [_product(i, f"2025 Topps Chrome Other Player Silver #{i}") for i in range(1, 251)]
    page2 = [
        _product(251, "2025 Topps Chrome Alpha Player Silver #251"),
        _product(252, "2025 Topps Chrome Beta Player Silver #252"),
    ]
    source.client.close()
    fake = _Client({1: page1, 2: page2})
    source.client = fake

    alpha = source.search("NFL", query="Alpha Player", limit=1)
    first_call_count = len(fake.calls)
    beta = source.search("NFL", query="Beta Player", limit=1)

    assert [row.external_id for row in alpha] == ["251"]
    assert [row.external_id for row in beta] == ["252"]
    assert first_call_count == 2
    assert len(fake.calls) == 2
    assert fake.calls[0][1] == {"limit": 250, "page": 1}
    assert fake.calls[1][1] == {"limit": 250, "page": 2}
