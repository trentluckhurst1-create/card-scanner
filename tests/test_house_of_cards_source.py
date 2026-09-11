from __future__ import annotations

import httpx

from card_scanner.sources.house_of_cards import HouseOfCardsSource


def _client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/shop":
            assert request.url.params.get("q") == "Trae Young"
            return httpx.Response(
                200,
                text=(
                    '<a href="/product/trae-young-optic-198">Trae Young</a>'
                    '<a href="/product/trae-young-blaster">Trae Young Box</a>'
                    '<a href="/product/trae-young-sold">Trae Young Sold</a>'
                ),
            )
        if request.url.path == "/product/trae-young-optic-198":
            return httpx.Response(
                200,
                text=(
                    '<meta property="og:image" content="https://cdn.example/trae.jpg">'
                    '<h1>2018 Panini Donruss Optic TRAE YOUNG Rated Rookie Choice Dragon #198 PSA 8</h1>'
                    '<div class="price">$249.95</div>'
                ),
            )
        if request.url.path == "/product/trae-young-blaster":
            return httpx.Response(
                200,
                text=(
                    '<h1>2018 Panini Donruss Optic Trae Young Basketball Blaster Box</h1>'
                    '<div>$199.00</div>'
                ),
            )
        if request.url.path == "/product/trae-young-sold":
            return httpx.Response(
                200,
                text=(
                    '<h1>2018 Panini Donruss Optic TRAE YOUNG Rated Rookie #198 PSA 8</h1>'
                    '<div>$189.00 Sold out</div>'
                ),
            )
        raise AssertionError(f"unexpected request: {request.url}")

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://www.houseofcardsnco.com.au")


def test_targeted_house_of_cards_search_emits_only_active_exact_ready_single() -> None:
    with _client() as client:
        rows = HouseOfCardsSource(client=client).search("NBA", "Trae Young", limit=10)

    assert len(rows) == 1
    listing = rows[0]
    assert listing.source == "houseofcards"
    assert listing.price == 249.95
    assert listing.currency == "AUD"
    assert listing.image_url == "https://cdn.example/trae.jpg"
    assert listing.identity is not None
    assert listing.identity.card_number == "198"
    assert listing.identity.grader == "PSA"
    assert listing.identity.grade == 8.0


def test_house_of_cards_fails_closed_for_broad_or_unsupported_searches() -> None:
    with _client() as client:
        source = HouseOfCardsSource(client=client)
        assert source.search("NBA", "", limit=10) == []
        assert source.search("NHL", "Trae Young", limit=10) == []
